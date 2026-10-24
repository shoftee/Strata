# Installing Strata for a user (instructions for AI agents)

This page is written for an AI coding assistant (Claude Code, Cursor, Codex, GitHub Copilot, ...) that a user asked to
set up Strata on their PC. Strata runs the Qwen3.8-Flash-Next model locally on one NVIDIA or AMD graphics card plus
system RAM (or on an Apple Silicon Mac), and serves an OpenAI- and Anthropic-compatible API on `http://127.0.0.1:8080`.
The human-oriented version of everything below is [INSTALL.md](INSTALL.md).

You install Strata from a checkout of this repository: `./setup.sh` on Linux, `START-HERE.bat` on Windows. It checks the
PC, gets or builds the engine for the graphics card, downloads the model and starts the server. A second run starts the
model again and downloads nothing twice.

Work through the steps in order. Tell the user what you are doing in plain words; they may not be technical.

## 0. Ground rules

- **Recommend an API key beyond this computer; do not force it.** The default is fine: the server listens on `127.0.0.1`
  only and needs no key. Only if the user asks for access from other devices, use `--host <address> --api-key <key>`
  (`STRATA_API_KEY` works too). Tell the user the key. Serving beyond `127.0.0.1` without a key is possible
  (`serve/server.py --no-api-key`): it warns that anyone who can reach the port can use the model and its tools. Do not
  put a tunnel or port forward in front of a server without a key unless the user asks for it.
- **Do not change the user's system beyond what setup does.** On Windows it needs no administrator rights. On Linux it
  uses `sudo apt` (or dnf/pacman) for Python with venv if it is missing, and on AMD also `build-essential` and `git`.
  You cannot type the user's password: when a `sudo` step is needed, ask the user to run it (for example
  `sudo apt install python3-venv build-essential git`) and then run setup again. Ask before installing drivers.
- **The model download is ~70 GB** (94 GB for Unsloth's UD-IQ4_XS, 111 GB for UD-Q4_K_XL). Confirm the user is fine with
  that before you start, especially on a metered connection.
- **The first run is long-running** (an hour or more on a slow connection), and it compiles the engine for your card
  (10-40 minutes, on AMD as much as on NVIDIA). Run it in the background or with a long timeout and poll its
  output; do not kill it because it is quiet for a while. It is resumable: running the same command again continues
  where it stopped.
- Setup recommends, it never forces. `--yes` takes the recommended answer to every question; a flag you name is the
  consent to the risk setup would otherwise stop at.

## 1. Check the PC

Requirements (details: [INSTALL.md](INSTALL.md#what-you-need)):

- **GPU:** NVIDIA RTX 20, 30, 40 or 50 series, or AMD Radeon RX 7900 XT / XTX, RX 7800 XT / 7700 XT, RX 9060 XT,
  RX 9070 / 9070 XT, Radeon AI PRO R9700, RX 6800 / 6900 series; 12 GB of VRAM or more (an NVIDIA card with 8 GB runs,
  slowly). GTX 10 series and older, and integrated GPUs, are not supported; Pascal / Volta cards (P40, V100) and some
  older AMD cards have experimental paths the user opts into ([OLDER_GPUS.md](OLDER_GPUS.md)). A **Mac** needs Apple
  Silicon (M1 or newer), macOS 15 or newer and 16 GB of memory or more ([MAC.md](MAC.md)).
- **Driver:** NVIDIA 580 or newer. AMD on Linux: the kernel's amdgpu driver; on Windows: a current AMD Adrenalin
  driver. If the driver is missing or too old, tell the user to update it (NVIDIA App / nvidia.com/drivers, or AMD
  Software) and restart; do not install drivers yourself unless they ask.
- **RAM:** 32 GB or more (see step 3). **Disk:** ~80 GB free, ideally on an NVMe SSD. **CPU:** x86-64 with AVX2.
  Without AVX2 (Xeon E5 v1/v2 and older) an engine built for a newer CPU refuses to start; building on the PC makes an
  experimental and slow engine (10-20 minutes): tell the user that before starting
  ([INSTALL.md](INSTALL.md#older-cpus-experimental)).
- **OS:** Windows 10/11, Linux x86-64 (Ubuntu 22.04/24.04 and Debian 12/13 are fully automatic), or macOS on Apple
  Silicon ([MAC.md](MAC.md) is the Mac path: the engine is built there with cmake).

To check by hand:

| What | Windows (PowerShell) | Linux | Mac |
| --- | --- | --- | --- |
| OS | `[Environment]::OSVersion` | `cat /etc/os-release` | `sw_vers` |
| NVIDIA GPU, VRAM, driver | `nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv` | the same | - |
| AMD GPU | `Get-CimInstance Win32_VideoController \| Select-Object Name, AdapterRAM` (AdapterRAM is capped at 4 GB; trust the model name) | `lspci \| grep -i -E 'vga\|display'`; VRAM: `cat /sys/class/drm/card*/device/mem_info_vram_total` (bytes); `rocm-smi` only if ROCm is installed | - |
| RAM | `(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB` | `free -g` | `sysctl -n hw.memsize` (bytes) |
| Free disk | `Get-PSDrive -PSProvider FileSystem` | `df -h .` | `df -h ~` |

If the PC does not meet them, say which part is missing and stop.

## 2. Get Strata

```
git clone https://github.com/Niko1221/Strata.git
```

Without git: download https://github.com/Niko1221/Strata/archive/refs/heads/main.zip and unzip it. Pick a drive with
enough free space: the model files go to a `Strata-data` folder next to the Strata folder (or `--data-dir <path>` on
another drive).

Then let setup look at the PC. It prints the GPU(s), driver, RAM, CPU, free disk and whether this PC can run Strata,
and installs nothing except Python and the `.venv` it needs to run:

```
Windows:  START-HERE.bat --check
Linux:    ./setup.sh --check
```

## 3. Pick the model

Setup recommends a size for this PC's memory. With `--yes` and no `--model` it takes that recommendation. Ask the user
whether they mainly want it for code - then the Coder is a good pick at any RAM size. Name the size yourself with
setup's flag names (they are not case sensitive):

| RAM | flags (with `--family`) | Notes |
| --- | --- | --- |
| 32 GB | `--family coder --model IQ1_M` | for code; with a 24 GB card Q2_0 and IQ2_XS also run (Strata picks the low-RAM mode) |
| 40 GB | `--model IQ2_XS` | or `Q2_0` (fastest); [Gyro-S](GYRO.md) fits a 32 GB PC too |
| 48 GB | `--model IQ3_XXS` | slower, better |
| 64 GB | `--model IQ3_S` (recommended) | the slowest and the best; `IQ2_XS` is faster |
| 96 GB+ | `--model IQ3_S` | `--family unsloth --model UD-IQ4_XS` (~4-bit, 94 GB, part of the experts read from the SSD under ~80 GB of RAM); `UD-Q4_K_XL` is experimental: NVIDIA only, NVMe SSD, 7-8.5 tokens/s on 64 GB |

`--family swift` (Swift 1.5, a fine-tune that thinks shorter; sizes IQ2_XS, IQ3_XXS, IQ3_S) is the alternative to
`qwen`; `--family gyro` is the smallest way to run the model. More: [MODELS.md](MODELS.md).

## 4. Set up, without questions

```
Windows:  START-HERE.bat --yes --family qwen --model IQ2_XS --vision yes
Linux:    ./setup.sh --yes --family qwen --model IQ2_XS --vision yes
```

Setup only installs: it writes the run config, prints the start command and returns. It never starts the server,
so your shell comes back when the install is done.

The flags (all of them: `START-HERE.bat --help`, `./setup.sh --help`):

| Flag | Meaning |
| --- | --- |
| `--yes` | take the recommended answer to every question (no prompts) |
| `--family qwen\|swift\|coder\|unsloth\|gyro\|nvfp4\|qwen36` | the model version |
| `--model Q2_0\|IQ2_XS\|IQ3_XXS\|IQ3_S\|IQ1_M\|Gyro-S\|Gyro-M\|UD-IQ4_XS\|UD-Q4_K_XL\|...` | the size (the Coder is IQ1_M, Unsloth UD-IQ4_XS or UD-Q4_K_XL) |
| `--context N` | context in tokens; default by VRAM: 32768 under 14 GB, 65536 under 20 GB, else 131072 |
| `--vision yes\|no\|gpu\|cpu` | let the model read pictures. Pass `yes` to get the best reader for the card (the CPU under 24 GB, the GPU from 24 GB, any make); `no` turns them off |
| `--gpu N` / `--gpus 0,1` / `--gpus all` | one card, or several sharing the model (default: the card with the most VRAM) |
| `--parallel N` | requests answered at the same time, 1 to 8 (default: one at a time) |
| `--backend cuda\|hip\|sycl` | NVIDIA, AMD or Intel engine; chosen by itself on a PC with only one kind of card |
| `--data-dir PATH` | where new model files go. Nothing is moved unless you add `--move-data`; the saved default folder changes only with `--move-data` or `--set-default-data-dir` |
| `--models-dir DIR`, `--gguf-dir DIR` | use GGUF files the user already has |
| `--port N` | the server's port (default: the one the install was set up with, 8080 for a new one) |
| `--host H --api-key K` | listen beyond this PC; keep a key when you do |
| `--source auto\|modelscope\|huggingface` | where the model files come from |
| `--setup` | install another model or change the settings of an installed one |
| `--check` | only check this PC and exit |

Notes:
- **Setup only installs** - it does not start anything, and your shell is yours again when it is done. Start the
  server yourself, in the background, as in section 6.
- **`--check` first** if you want to see what setup found about this PC before it installs anything.
- **Setup always compiles the engine** for the card in this checkout, so a card that is not on the list in step 1 is
  refused before the model download: there is nothing to fall back to.
- **Linux:** nothing needs `sudo` except the packages in step 0. **Windows:** the first start may ask once whether to
  allow Strata on the network when the server listens beyond `127.0.0.1`.
- **AMD on Windows:** only the AMD driver is needed, and setup does not build the AMD engine there: build it with
  `tools\hip\build_windows.bat` first ([AMD_HIP.md](AMD_HIP.md)). It has not been run with a model on a real AMD card on
  Windows by us: ask the user to report how it runs.
- **AMD on Linux:** setup installs ROCm into `.venv` (~10 GB, no sudo) unless a system ROCm 7 exists, and compiles the
  engine for the card (10-20 minutes, once).
- **The build tools are missing:** setup offers to install them (20-40 minutes, a compiler and the CUDA toolkit);
  `--yes` accepts. Ask first.

## 5. While it downloads, tell the user

- It downloads about 70 GB from Hugging Face; how long depends on their connection (at 100 Mbit/s roughly 1.5-2
  hours). It can be stopped and continues where it left off.
- Then it prepares the model for their PC (a few minutes).
- **When the model starts, the PC can be slow or stop responding for 1-3 minutes** (longest the first time): Strata
  loads 35-55 GB into RAM and locks part of it for the graphics card. That is normal; they should not close the window.
- Nothing leaves their PC: the model runs locally.

## 6. Start it and check that it is serving

Setup printed the start command (`Start the server with: ...`): `serve/server.py` with the run config it wrote. The
config is named for the family tag plus the size, lower case: `strata-iq2_xs.json`, `strata-swift-iq2_xs.json`,
`strata-coder-iq1_m.json`, `strata-unsloth-ud-iq4_xs.json`. Start it the way the user will, and keep it out of your
own shell:

```
Windows (PowerShell):  Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "serve\server.py", "--engine", "strata", "--config", "strata-iq2_xs.json", "--port", "8080"
Linux:                 nohup .venv/bin/python serve/server.py --engine strata --config strata-iq2_xs.json --port 8080 > strata-server.out 2>&1 &
```

The engine log is `strata-<model>.log` in the Strata folder. To stop the model, close the window (or end the process);
to change what it runs, run setup again with `--setup`.

## 7. Verify

The HTTP server answers once the model is loaded (30-90 s on later starts, a few minutes the first time). Poll:

```
curl http://127.0.0.1:8080/health
```

It returns `{"status": "ok", "model": ..., "max_context": ..., "images": ..., "api_key": ..., "loaded": true, ...}`.
Then:

```
curl http://127.0.0.1:8080/v1/models
curl http://127.0.0.1:8080/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\": \"strata\", \"messages\": [{\"role\": \"user\", \"content\": \"Say hello in five words.\"}], \"max_tokens\": 64, \"reasoning_effort\": \"none\"}"
```

With an API key, add `-H "Authorization: Bearer <key>"`.

## 8. Connect the user's apps

- **Browser:** `http://127.0.0.1:8080` - Chat, a live Monitor, and About (settings and the client addresses).
- **Any OpenAI-compatible app or agent:** base URL `http://127.0.0.1:8080/v1`, any API key (or the configured one),
  any model name.
- **Anthropic-compatible apps:** base URL `http://127.0.0.1:8080`, without `/v1`. Those apps add `/v1/messages`
  themselves.
- **Codex CLI and other Responses API apps:** `http://127.0.0.1:8080/v1/responses` (stateless; Codex's
  `config.toml`: [DETAILS.md](DETAILS.md#the-responses-api-and-codex-cli)).
- **Claude Code:** `ANTHROPIC_BASE_URL=http://127.0.0.1:8080`, `ANTHROPIC_MODEL` set to a Claude model name it knows
  (Strata ignores the name), and any `ANTHROPIC_AUTH_TOKEN` (or the configured key).
- **Thinking level:** `"reasoning_effort": "none" | "low" | "medium" | "high"` (default high).
- Strata answers one request at a time; `--parallel N` decodes up to N together ([BATCHING.md](BATCHING.md)). API
  details: [DETAILS.md](DETAILS.md#using-it).

## 9. When something fails

| Symptom | What to do |
| --- | --- |
| `the NVIDIA driver is too old` | The user updates the driver (NVIDIA App or nvidia.com/drivers) and restarts; run the command again. |
| Download or install stopped | Run the same command again; it continues where it stopped. |
| No engine for this PC | The card is not one the engine builds for. Check the card against the list in step 1; `--backend hip` or `--backend sycl` chooses another backend, and `--check` shows what setup found. |
| `port 8080 is already in use` | Strata is already running (check `/health`), or start on another port with `--port 8081`. |
| Very slow, disk busy, or "the engine stopped unexpectedly" | Not enough free RAM: close programs, or choose a smaller size (`Q2_0` or `IQ2_XS`). |
| `ExpertCache: cudaMalloc(...) failed: out of memory` with free VRAM (Windows) | The page file is off or tiny: set a fixed size (Custom size, the same initial and maximum size, e.g. 65536 MB) and restart; a page file Windows grows on demand ("System managed") may not grow in time (#60). |
| `prompt ... exceeds the context` | Start again with a bigger `--context`. |
| No AMD GPU found (Linux) | The amdgpu driver lists no GPU; check the card and driver. Integrated GPUs are not supported. |

More: the [full troubleshooting table](DETAILS.md#troubleshooting). If it still fails,
collect `strata-<model>.log` from the Strata folder, what setup printed, and the card and driver, and suggest an issue
at https://github.com/Niko1221/Strata/issues.
