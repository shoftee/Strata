# Security

## Reporting a vulnerability

Please report anything that should not be public until it is fixed **privately**, through GitHub's private
vulnerability reporting: the repository's **Security** tab, **Report a vulnerability**
([direct link](https://github.com/Niko1221/Strata/security/advisories/new)). Say what you found, how to reproduce it
(the request, the config keys involved, the Strata version), and what an attacker gains. We answer there, fix it in
a release, and credit you in the advisory unless you ask us not to.

Ordinary hardening ideas and findings that are safe to discuss in public are welcome as an
[issue](https://github.com/Niko1221/Strata/issues) (#544 collects audit findings) or as a pull request, which we
review like our own code.

Supported: the latest release. Fixes go into the next release, not into older ones.

## What the server exposes

Strata runs a model on your PC and serves it over HTTP (`serve/server.py`). Out of the box it is reachable from
this PC only. The details and every setting are in [docs/DETAILS.md](docs/DETAILS.md) ("From other devices",
"Host names", "Web pages without an API key", "Tools from MCP servers").

- **Where it listens.** `127.0.0.1` by default: only this PC. `--host 0.0.0.0` (or `"host"` in
  `strata-<model>.json`) opens it to your network, and the server then warns when no API key is set.
- **API key.** `--api-key`, `STRATA_API_KEY` or `"api_key"` in the run config sets one (several keys: separate
  them with commas, or use a list in the config). It is required on `/v1/*` and on every endpoint that shows the
  model's state, requests or answers (`/status`, `/metrics`, `/settings`, `/mcp`, `/props`, `/slots`,
  `/api/requests`, `/config`) and on every `POST`. It is compared in constant time. You can serve without a
  key on purpose - `--no-api-key` (or `"api_key": "none"`) - and the server then warns once and never refuses.
  Set a key before you open the server to your network or put a tunnel in front of it.
- **Host check (DNS rebinding).** Without an API key the server answers only requests whose `Host` is a name
  it knows (`localhost`, an IP address, the address it listens on and, when it listens beyond this PC, this PC's
  name). Others get 403. `"allowed_hosts"` (or `STRATA_ALLOWED_HOSTS`) adds names; with an API key the key
  decides and this check is off.
- **Origin check.** Without an API key, a browser `POST` to `/v1/*` from another web site's page (it carries an
  `Origin` header) gets 403 unless that origin is Strata's own page, a page on `localhost` or an allowed host,
  or listed in `"trusted_origins"` / `"cors_origins"`. Changing settings (`/settings`, and `/config`: the few
  run config keys the page's Model settings may change - never the network, key, MCP or program keys), loading
  and unloading the model (`/load`, `/unload`), saving and restoring conversations (`/slots/…`), the VRAM
  reserve (`/v1/vram`) and the MCP tools are accepted only as JSON from Strata's own page (or an origin in
  `"trusted_origins"`), so a page elsewhere cannot change settings or run tools.
- **CORS** is off unless `"cors_origins"` lists origins, and then only for `/v1/*`.
- **Telemetry key.** A second key, if you set one (`"telemetry_read_key"` in the run config, or
  `STRATA_TELEMETRY_KEY`), unlocks exactly one endpoint: `GET /v1/telemetry`, a read-only snapshot of the
  model's state and the hardware readings. It cannot run the model or change anything, and the server refuses
  to start if it is the same as the API key.
- **MCP tools** are opt-in: only the servers you put in the run config (`"mcp_servers"`, or `--mcp-config`),
  only for requests from Strata's own page that ask for them. They run with your user's rights and can read and
  change files on this PC, and the model decides when to call them.
- **The request monitor** (`/api-monitor`, which keeps the last prompts and answers in memory) is off unless
  `"api_monitor": true` is set. Apart from it, the engine keeps a conversation cache in this PC's memory - the
  tokens of recent conversations and what the model had already computed from them, kept so the next turn does
  not have to read them again. Nothing at the endpoints shows them, and they are gone when the server stops.

## What runs on your PC

Three things, all as ordinary processes of your own user. Nothing installs a service or a background updater:

- **The installer** (`setup.py`, started by `START-HERE.bat` or `./setup.sh`). It runs when you run it: it
  checks the PC, builds or fetches the engine for your card, downloads the model, writes a run config
  (`strata-<model>.json`) and starts the server. What it downloads, and how that is checked, is below.
- **The server** (`serve/server.py`). One HTTP server, on `127.0.0.1` (port 8095 unless `--port` says
  otherwise), so only this PC reaches it. Beyond that an API key is recommended, and the `Host`, `Origin` and
  content-type checks above hold even when you serve without a key.
- **The engine and its helpers.** The server starts the engine (`strata --serve`), with it the picture reader
  (`strata-vision`) when the model has one, and one image generator process per picture job when the config
  asks for image generation. They are local processes with no network listener of their own: the server starts
  them with its own pipes and talks to them through those, not over the network. The engine and the picture
  reader stop when the server stops: by a shutdown message over that pipe, and on Windows each child also sits
  in a job object that ends it even if the server dies without cleanup (`serve/winjob.py`).

## What the installer downloads, and how it checks it

- **The model files** come from Hugging Face at pinned revisions, and every file has its size and SHA-256
  written in `setup.py`. A file that does not match is deleted and the install stops.
- **llama.cpp's source** (used to build the engine) is fetched as the archive of one pinned commit
  (`LLAMA_CPP_COMMIT`), from GitHub over HTTPS.
- **The engine** is not downloaded at all: setup compiles it for your card from this checkout (and from the
  llama.cpp source above), so the code that runs is the code you cloned.
- **ModelScope**, if you ask for it (`--source modelscope`, for networks where Hugging Face cannot be
  reached), serves a repository's current files rather than our pinned revision. Each file is then checked
  against the SHA-256 ModelScope itself publishes for it; where ModelScope publishes no hash, setup says the
  file is not verified.
- **One switch turns a check off**, and it warns: `STRATA_ALLOW_UNPINNED=1` takes a model file whose pinned
  revision is gone from Hugging Face from the current files, without a hash check.

Those checks have a limit, said plainly. The model files' hashes are written in this code, so you can read
them, but they vouch only for the exact revision they name - a file that matches the hash of a revision that
was itself replaced on Hugging Face looks fine. The engine has no download to trust: it is built from the
source you clone, which is the route that checks nothing against a publisher and everything against your own
reading.

## Getting a new version

Nothing on your PC updates itself: the model's starts download nothing, and a start refuses to install a
package while the model runs. A new version is a step you take yourself - `git pull` in this checkout, then
start the model again: setup sees that the engine's source changed and compiles the new one (a few minutes,
only the changed files), and it never touches your model files or a saved tuning.

## How to get Strata

Two routes, and both start from a checkout you can read. The everyday one:

```sh
git clone https://github.com/Niko1221/Strata.git && cd Strata
./setup.sh --yes                # Linux and Mac
START-HERE.bat --yes            # Windows, from a command prompt in this folder
```

The first run installs the Python packages, compiles the engine for your card from this source, downloads
the model (tens of GB) and starts serving; it prints the addresses when the model is
up, and closing that window stops it. A later run just starts the model again.

The other route builds the engine yourself. It is a normal CMake project, and `docs/INSTALL.md` gives the
full line for each card family; the short form for NVIDIA is:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON && cmake --build build --target strata -j8
```

and then the server starts from a run config. A Mac builds its engine with cmake this way in any case
([docs/MAC.md](docs/MAC.md)); the AMD and Intel cards' builds are the same kind of cmake build
([docs/AMD_HIP.md](docs/AMD_HIP.md)).

If you want to trust what runs on your PC, read the source you build: the download hashes, the endpoints and
every check named on this page live in `setup.py`, `serve/server.py` and `strata_control/` in the very checkout
you build from.

Strata has not had an outside security audit yet.
What Strata downloads, when it uses the internet, what stays on your PC and how downloads are checked is written up in [docs/SAFETY.md](docs/SAFETY.md).
