# Is Strata safe and private?

This page says what Strata downloads, where from, when it uses the internet, what stays on your PC and how the downloads
are checked. Everything here comes from reading the code of this version. Each section names the files, so you or anyone
you trust can check it. Where Strata does less than you might hope, the page says so.

## At a glance

- **Your chats, prompts, files, pictures and models stay on your PC.** They leave only when you choose it: you give the
  server an address other devices can reach, or a program you connect to it sends them somewhere itself.
- **There is no telemetry.** Strata sends no usage data, no crash reports and no analytics, and has no account to sign in to.
- **Starting and running a model never downloads anything.** The install is a step you run; a running server refuses to
  download at all.
- **The server listens on your PC only.** Reaching it from another device means giving it another address of this PC, and
  there an API key is recommended.
- **Once a model is downloaded, Strata runs without internet.** Starting, loading, serving and chatting need no connection.
  A first model install also fetches llama.cpp's preparation scripts.
- **Downloads are checked.** Every model file has a fixed SHA-256 and size written in the code (the details are
  [below](#how-downloads-are-checked)). The engine is not downloaded: it is compiled from this checkout.
- **The code is open.** Anyone can read it, and security problems go to [SECURITY.md](../SECURITY.md).

## Does Strata phone home?

No. A search of the engine server, the installer and the tools found no analytics library, no crash reporter and no code
that reports usage anywhere.

Some things sound similar and stay on your PC:

- The Monitor, `/metrics` and `/v1/telemetry` show hardware readings (temperature, speed, memory) to you. They are served
  from your own PC, and they need your API key when you set one.
- The engine log `strata-<model>.log` and the server's output are files on your disk. Nothing sends them. You decide
  whether to attach one to a bug report.
- Strata's page loads no font, script or tracker from the internet: everything it shows comes from the server on your PC
  (`serve/web/`).

Like any download, each connection below shows the other side your IP address and the file you asked for.

## When Strata uses the internet

| What | Where it goes | When |
| --- | --- | --- |
| Model files, the picture reader, the speed-up layer (MTP) | huggingface.co, or the mirror in `HF_ENDPOINT` if you set one | When you install a model |
| The same files from ModelScope, for PCs that cannot reach Hugging Face | modelscope.cn | Only if you ask for it (`--source modelscope`). Strata never switches to it by itself |
| The engine for your graphics card | compiled on your PC, from this checkout and the pinned llama.cpp commit; its build tools come from your distribution, from PyPI (CMake, Ninja), from NVIDIA's CUDA repository or from AMD's ROCm wheels | During setup |
| llama.cpp source code (a fixed commit) | github.com/ggml-org/llama.cpp | During a model install, if it is not on your PC yet. Strata uses only its model-preparation scripts |
| Python and its packages | python.org or winget on Windows, your distribution's packages on Linux, then PyPI with pinned versions; on Ubuntu and Debian, NVIDIA's apt key and packages for the CUDA toolkit; AMD's ROCm wheels; the Vulkan SDK from LunarG; llama.cpp and stable-diffusion.cpp source from GitHub | Only while you run the setup |
| An image link in an API request | The address in the link | Only when a program sends your server a request with an `http(s)` image link. `--offline` refuses it |
| Remote tool servers (MCP) | The address you put in the run config | Only when you add one |

That is the full list found in the code. Some details:

- **Nothing checks for updates in the background.** Nothing runs at logon and nothing opens a port. A new version arrives
  when you update this checkout (`git pull`) and run setup again. With no connection, a download says so and nothing else
  happens.
- **Starting and serving never download.** `serve/server.py` fetches nothing: a model that is not installed is reported,
  not fetched. The downloader (`strata_control/acquisition.py`) refuses to run when the environment sets
  `STRATA_NO_ACQUIRE=1`; only the install step downloads, and only the files it needs.
- **The engine itself has no network code.** The part of Strata that runs the model (`src/`, `include/`, `sycl/`, `metal/`)
  contains no networking.

## What stays on your PC

- **Chats, prompts, attached files and pictures** are handled by the engine on your PC. The page keeps a conversation, its
  settings and the key you typed in that browser's local storage, not on the server (`serve/web/app.js`); a picture is not
  kept, only its name.
- **Your API key** lives in the run config (`"api_key"`) or in the environment (`STRATA_API_KEY`), readable by your own
  account. It is not encrypted.
- **The server listens on `127.0.0.1`**, this PC only: that is `--host`'s default and what the run config holds unless you
  change it (`serve/server.py`).
- **Wider access is your choice, and it should come with a key.** `--host 0.0.0.0` (or `"host"` in the config) answers the
  local network too; the server warns when it listens beyond `127.0.0.1` without a key, and `--no-api-key` serves without
  one after that warning. Which pages may talk to it is decided by `"allowed_hosts"`, `"trusted_origins"` and
  `"cors_origins"` in the config, and a request that is not from Strata's own page cannot load or unload the model or
  overwrite a saved conversation.
- **Programs you connect** (Claude Code, Codex, and so on) are separate programs with their own network behaviour. Strata
  does not control what they send.

## What setup does to your PC

- On Linux it uses `sudo apt` (or dnf or pacman) for Python with venv when it is missing, and for the build tools when it
  has to compile an engine. It says what it installs, and it never runs without telling you.
- Everything else stays inside the Strata folder: `.venv/` (Python and its packages), `engine/`, `third_party/`, the build
  folders, the run config `strata-<model>.json` and the log
  `strata-<model>.log`. The model files go to `Strata-data` next to it, or where `--data-dir` puts them.
- It does not install a service, does not register anything to run at logon, and does not open a firewall port. On Windows
  the firewall may ask you once when the server starts listening beyond `127.0.0.1`.

## How downloads are checked

**Model files.** Every model file that `setup.py` downloads has a fixed SHA-256 and size, written in the code, so the check
needs no network: the main Qwen3.8-Flash-Next files (Q2_0, IQ2_XS, IQ3_XXS, IQ3_S), Swift 1.5, the Coder, the Unsloth sizes,
the Gyro files, Qwen3.6, the NVFP4 packs, the picture reader, the image model files and the speed-up layer (MTP, tensor by
tensor). A file that does not match is deleted and the install stops. A file whose size on the server is not the pinned
size stops it before the download starts.

- If the pinned version of a file is gone from Hugging Face, the install stops and says to update Strata. It does not take
  the repository's current file instead. A tester can set `STRATA_ALLOW_UNPINNED=1` to take the current file anyway, without
  the check. It is off by default, and setup says so when it is set.
- Starting a model does not check its files, and running setup again for a model you have does not download or hash them
  again. A file installed before these hashes existed is kept as it is.
- Files from ModelScope are checked against the same fixed SHA-256. ModelScope serves a repository's current files, so a file
  it has changed fails the check. A file without a pin is checked against the hash ModelScope publishes, and setup warns
  when it publishes none.
  (`setup.py`: `REPO_PINS`, `download`, `verify_sha256`; `tools/mtp_fetch.py`; `tools/image/qimage.py`.)

**The engine is not downloaded.** `setup.py` compiles it from this checkout with the pinned llama.cpp commit, and prints the
commands it runs. Nothing checks a signature or a published hash, because there is no engine archive to check: the code that
runs on your card is the code in the folder you cloned. An update never replaces your models or a saved tuning.

**Building the engine yourself** is the same build: the engine is an ordinary CMake project, and setup only runs the
compilers for it.

**What the checks do not cover.** A model file's hash proves the file matches the pinned revision, not that the revision is
the one its author meant: a file replaced by someone who controls the repository at that revision would pass. The engine has
no such check at all - it is whatever this checkout says, so read what you build.

## Open source and reporting a problem

Strata is MIT-licensed and the whole code is at [github.com/Niko1221/Strata](https://github.com/Niko1221/Strata). Read it, build
it and compare. Strata has not had an outside security audit yet.

To report a security problem, use GitHub's private reporting (the repository's **Security** tab), as described in
[SECURITY.md](../SECURITY.md). Ordinary questions and ideas can go to an
[issue](https://github.com/Niko1221/Strata/issues).

## Where to check this in the code

| Topic | Files |
| --- | --- |
| Model downloads and pins | `setup.py`, `tools/mtp_fetch.py`, `tools/image/qimage.py` |
| The engine build | `setup.py` (`build_engine`, `build_engine_hip`, `restamp_engine`) |
| Downloads refused while running | `strata_control/acquisition.py` |
| What the server exposes, and to whom | `serve/server.py` (`--host`, `--api-key`, `_own_page`, `allowed_hosts`, `trusted_origins`, `cors_origins`) |
| The page and what it keeps | `serve/web/app.js` (the browser's local storage) |
| What the setup installs | `setup.py`, `setup.sh`, `START-HERE.bat` |
