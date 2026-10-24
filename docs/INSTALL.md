# Installing Strata

Everything about installing, starting, updating and configuring Strata, on Windows, Linux and Mac, with an NVIDIA
or an AMD graphics card or an Apple Silicon Mac. The short version is in the [README](../README.md#install). An AI
coding assistant can do all of this for you with [AI_SETUP.md](AI_SETUP.md).

There is one way in: a copy of this repository and its installer. `START-HERE.bat` on Windows, `./setup.sh` on
Linux. It checks the PC, gets or builds the engine for the graphics card, downloads the model and starts the server.
A Mac builds its Metal engine with cmake ([MAC.md](MAC.md)).

> **On this page:** [What you need](#what-you-need) · [Windows](#install-on-windows) · [Linux](#install-on-linux)
> ([build from git](#build-from-git-on-linux-to-try-a-pull-request-or-change-the-code)) · [Mac](#mac) ·
> [AMD cards](#amd-cards) · [Several cards](#two-or-three-cards) · [Older CPUs](#older-cpus-experimental) ·
> [Updating](#updating) · [Where things are stored](#where-things-are-stored) ·
> [Setup's questions](#setups-questions) · [Tuning](#tuning-for-your-pc) · [All options](#options-without-questions)

## What you need

| | |
| --- | --- |
| **GPU** | **NVIDIA** RTX 20, 30, 40 or 50 series, **12 GB VRAM or more** (8 GB runs, slowly). Measured on an RTX 5070 and an RTX 3090; RTX 20 (Turing, since 0.1.27) was tested by a contributor on an RTX 2070. **AMD** Radeon RX 7900 XT / XTX, RX 9070 / 9070 XT and Radeon AI PRO R9700 (validated), RX 7800 XT / 7700 XT and RX 9060 XT (validated by their owners), RX 6800 / 6900 series (community-reported), with 12 GB of VRAM or more. See [AMD cards](#amd-cards). |
| **RAM** | Enough for the size you pick ([which model](MODELS.md#pick-by-memory)); **64 GB** runs every size. A big GPU makes up for less RAM - the [low-RAM mode](MODELS.md#a-big-graphics-card-and-little-ram). |
| **CPU** | x86-64 with AVX2 (any Intel/AMD desktop CPU from the last ~8 years). AVX-512 (Ryzen 7000/9000) is a bit faster. Older CPUs without AVX2 are experimental and slow: [Older CPUs](#older-cpus-experimental). |
| **Disk** | ~70-80 GB free for the model, ~6 GB for the MTP layer (+1 GB with images); the engine and the Python environment take another 1-3 GB. Q2_0 on an AVX-512 CPU also writes a one-time ~40 GB copy of its experts for the fast CPU kernel. On Linux with an AMD card, ROCm takes ~10 GB more when setup installs it. An NVMe SSD is strongly recommended: it makes the first start much faster. |
| **OS** | Windows 10/11, Linux (Ubuntu 22.04/24.04 and Debian 12/13 get everything installed automatically; Fedora and other distributions work with their own packages), or a Mac with Apple Silicon (M1 or newer) and macOS 15 or newer ([Mac](MAC.md)). |
| **Driver** | **NVIDIA:** a current driver, version 580 or newer ([nvidia.com/drivers](https://www.nvidia.com/drivers) or the NVIDIA App). **AMD:** on Linux the kernel's amdgpu driver (no ROCm install needed); on Windows a current AMD Software: Adrenalin Edition driver ([amd.com/support](https://www.amd.com/en/support)). |

The driver is the only thing you install yourself. Setup sets up the rest, the first time: Python 3.12 if you
have none (for your user account, no admin), a private Python environment in `.venv/`, the Strata engine (compiled
for your card), the model and the MTP draft layer. It installs the build tools it needs (Visual Studio Build Tools +
CUDA Toolkit on Windows, `build-essential` + CUDA on Ubuntu; asks first; 20-40 minutes once) and compiles the engine
for your GPU. On Linux with a Radeon card it compiles the engine too ([AMD cards](#amd-cards)). More:
[details](DETAILS.md#before-you-start).

The normal Python install uses `requirements.txt` and does not install CMake or Ninja. If setup has to compile an
engine or image encoder, it uses existing CMake/Ninja tools when available and installs missing pinned helpers from
`requirements-build.txt` into `.venv`. An older `.venv` keeps any build helpers it already has; setup does not remove
packages during an update.

## Install on Windows

1. [Download this project](https://github.com/Niko1221/Strata/archive/refs/heads/main.zip) and unzip it (or
   `git clone` it).
2. Double-click **`START-HERE.bat`**.
3. Answer a few questions - or just press Enter each time for the recommended choice ([the questions](#setups-questions)).

Then it downloads everything (the model is ~70 GB, so the first time takes a while - you can stop and it picks up
where it left off) and **starts the model**. Your browser opens the Strata page at `http://127.0.0.1:8080`.

> **While the model starts, your PC can be slow or stop responding for 1-3 minutes** (longest the first time): Strata
> loads 35-55 GB into your RAM and locks part of it for the graphics card. That's normal - wait, and don't close the
> window. The window tells you what it is doing.

**Next time**, just double-click `START-HERE.bat` again: it starts right away (30-90 s to load the model), nothing is
downloaded twice. Close its window to stop the model. `SETUP.bat` (the same as `START-HERE.bat --setup`) installs
another model or changes the settings. Starting Strata from Task Scheduler at logon needs two task settings, or the
start is 24x slower: [Running it at startup](DETAILS.md#running-it-at-startup-task-scheduler).

## Install on Linux

```bash
./setup.sh
```

The same questions, the same automatic install (it uses `sudo apt` for Python and, only if it has to compile, for
the build tools), and the same start: `http://127.0.0.1:8080`. Later runs of `./setup.sh` (or `./run-<model>.sh`)
start the model directly; `./setup.sh --setup` installs another model or changes the settings. Other distributions,
WSL and compiling: [details](DETAILS.md#linux).

On Nix/NixOS, you can use the flake:

```bash
nix develop -c ./setup.sh
```

### Build from git on Linux (to try a pull request or change the code)

You do not need anything else: the source install builds the engine on your PC and keeps everything in the checkout,
so you can edit, rebuild and test.

```bash
git clone https://github.com/Niko1221/Strata.git && cd Strata
./setup.sh              # first run: .venv, the engine build (build/, or build-hip/ on a Radeon), the model, then it serves
```

- **What it needs:** `git`, a C++ compiler and `cmake` (setup installs the build tools through `sudo apt` on
  Debian and Ubuntu; elsewhere install them first), and the CUDA Toolkit for NVIDIA or ROCm with the HIP compiler for
  a Radeon card ([AMD_HIP.md](AMD_HIP.md)). Python goes into `.venv` of the checkout.
- **After you change the code:** run `./setup.sh` again. It compiles only what changed and starts the model. To
  compile without starting the model: `./setup.sh --no-start`. By hand, the build folder is an ordinary CMake build:
  `cmake --build build --target strata -j8` (`build-hip` for a Radeon card; the options are in
  [AMD_HIP.md](AMD_HIP.md)).
- **To try a pull request:** `git fetch origin pull/<number>/head:pr-<number> && git checkout pr-<number>`, then
  `./setup.sh`. `git checkout main` goes back; the next `./setup.sh` rebuilds.
- **Settings for the engine** (for example `STRATA_HIPBLASLT_TUNING=/path/to/table.txt`) go into the `"env"` object of
  `strata-<model>.json`, which `./setup.sh` writes next to the checkout. `./run-<model>.sh` starts the model with it.
- **Only compile, without the installer:** the engine is a normal CMake project. For NVIDIA:
  `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=native &&
  cmake --build build --target strata -j8`. The options, and the flags setup passes, are in `setup.py` (search for
  `-DSTRATA_`).

## Mac

On an Apple Silicon Mac with macOS 15 or newer the Metal engine is built on the Mac: install Apple's Command Line Tools
once (`xcode-select --install`), build the engine with cmake, and start the server from a run config. The build
commands, the metal-cpp and llama.cpp folders it needs, which size fits which memory, and how to serve it:
[MAC.md](MAC.md).

## AMD cards

Setup picks the AMD engine for a Radeon card by itself. The steps are the same as with NVIDIA: `START-HERE.bat` on Windows, `./setup.sh` on Linux. Setup finds the Radeon
card and chooses the AMD (HIP) engine by itself on a PC with no NVIDIA card Strata can use; `--backend hip` chooses
it on a PC that has both. Supported cards: RX 7900 XT / XTX (gfx1100), RX 7800 XT / 7700 XT (gfx1101), RX 9060 XT
(gfx1200), RX 9070 / 9070 XT and Radeon AI PRO R9700 (gfx1201), and the RX 6800 / 6900 series (gfx1030). Integrated
Radeon GPUs are listed as not supported.

On Linux setup uses a system ROCm 7 when there is one, or installs ROCm into `.venv` from AMD's wheels (~10 GB, no
sudo), and compiles the engine on your PC for the card (10-20 minutes, once; it needs a C++ compiler and git:
`sudo apt install build-essential git`). Several AMD cards share the model with `--gpus`, as on NVIDIA.

What differs from NVIDIA for now: `--calibrate` is NVIDIA-only, and Unsloth's 4-bit model needs an NVIDIA card. Measurements per card, the
build by hand and the tuning tables: [AMD_HIP.md](AMD_HIP.md).

## Two or three cards

**Two or three NVIDIA cards?** Just run `START-HERE.bat`: it lists your cards, says which ones Strata can use, and
asks whether to share the model across them (recommended when two can). An install made on one card asks once at
its next start. Or choose yourself: `START-HERE.bat --gpus 0,2` (both, remembered), `--gpus all`, or `--gpu 0` (one
card, this start only). Each card keeps the experts of its own layers, and prompts flow through the cards in a
pipeline: on an RTX 5080 + RTX 3090 prompts were read 18-20% faster than on the 5080 alone, decoding on par.
Every card must be an RTX 20 series or newer with 8 GB or more. See [MULTI_GPU.md](MULTI_GPU.md).

**Several AMD cards:** setup takes one card (the one with the most VRAM, or `--gpu N`) unless you name more:
`--gpus 1,0` splits the model's layers across them, the faster card goes last and is the Main card (`--gpu-roles 1=main,0=helper` says it yourself; docs/MULTI_GPU.md; numbers as setup lists them). A
split pays only when no single card holds the model's experts ([AMD_HIP.md](AMD_HIP.md#rdna4-gfx1201)).

## Older CPUs (experimental)

Strata's engine needs AVX2 (Intel Haswell 2013, AMD Zen 2017 or newer). Since 0.1.39 an older CPU - AVX
only (Sandy Bridge / Ivy Bridge, Xeon E5 v1/v2, AMD Bulldozer) or SSE4.2 only (Nehalem / Westmere, Xeon X5600) - runs
as an **experimental** build that setup compiles on that PC. Run setup as usual: it says the CPU has no AVX2, warns
that this is experimental and slow, and compiles the engine (10-20 minutes, once; Windows needs the Visual Studio Build
Tools and the CUDA Toolkit, which setup offers to install). It does not stop. An engine compiled for a CPU with AVX2
still refuses such a CPU, and says so.

What differs in that build (`STRATA_ISA_FLOOR=avx` or `none`, chosen from the CPU):

- ggml-cpu is compiled for AVX or SSE4.2 instead of AVX2, and the CPU's share of the experts runs on its kernels.
  Strata's own AVX2 / AVX-512 kernels stay in the program but are used only on a CPU that has them.
- Only the i-quant models' packs run (every model setup installs on such a CPU); the AVX-512 Q2_0 pack does not.
- Speed: the GPU part is unchanged and the CPU part is slower, so a GPU with more VRAM (more experts cached there)
  helps most. With the older paths forced on a Ryzen 5 7600 + RTX 5070 and the expert cache held at 1500 slots, greedy
  decode went from 26 to 11-17 tok/s with the AVX build and to 3.5-3.8 tok/s with the SSE4.2 build (Coder and IQ3_XXS,
  10 prompts each, one run). An old Xeon with DDR3 will be slower than these.
- Untested on a real old CPU by us. It was checked here by forcing the older paths on a Ryzen 5 7600
  (`STRATA_FORCE_ISA=avx` or `sse`): the answers were sane and passed the engine's checks, but not the same token for
  token as the normal build (ggml-cpu rounds the CPU experts differently, as the AVX2 kernel does from the AVX-512
  one). Contributors ran earlier versions of the same approach on a Xeon E5-2680 (2.87 tok/s with a GTX 1080 Ti)
  and on Xeon E5-2687W / X5690 machines.
- AMD cards: Linux only (setup compiles the AMD engine there anyway); NVIDIA on Windows and Linux.
- Two-socket Xeons: memory on the other socket is slow; keep the RAM on one CPU if you can.

By hand: `cmake ... -DSTRATA_ISA_FLOOR=avx` (or `none`) builds it; `STRATA_ISA_FLOOR=avx` set for setup builds it on
any PC (to try it). Problems and results on real hardware are welcome as GitHub issues.

## Updating

In a `git clone`: `git pull`, then run `START-HERE.bat` (Linux: `./setup.sh`) as usual. Setup sees that the engine's
source changed and compiles the new one (a minute or two for the changed files); if that compile fails, it says so and
starts the engine you had. Close the model's window first: a running engine cannot be replaced. Setup updates the
Python packages and each installed model's settings as it goes; the model files are not touched and no question is
asked. In a copy that was downloaded as a zip, download the new zip and unzip it anywhere instead: such a copy cannot
fetch new files itself.

The model files are kept in a `Strata-data` folder next to your Strata folder, so a new copy finds them and sets
itself up the same way - nothing big is downloaded again. To only compile the new engine without starting the model,
run `./setup.sh --no-start` (Windows: `START-HERE.bat --no-start`).

An update never downloads, replaces or deletes your model files or a saved tuning. What Strata downloads and how it
checks it: [SAFETY.md](SAFETY.md).

## Where things are stored

- **Your chats: only in your browser.** The Chat tab keeps the conversation, its settings and the API key you typed
  in the browser's local storage (`strata.*` keys) - not on the server and not in the Strata folder. Pictures are not
  kept, only their names. Another browser or a private window starts empty; clearing the site's data deletes them.
- **How the model starts:** `strata-<model>.json` in the Strata folder (context, GPUs, host, API key, ...), written
  by setup; next to it `run-<model>.bat` / `.sh`, the log `strata-<model>.log` and, when you use "Use for other
  apps too", `strata-<model>.shared-settings.json`. Running setup again for the same model (another context, say)
  rewrites the keys setup writes (`exe`, `args`, `port`, `gpu`, `host`, `api_key`, `vision`, ...) and keeps the
  ones you added (`sampling`, `mcp_servers`, `mcp`, `cors_origins`, ...); the earlier file is kept as
  `strata-<model>.json.bak` (0.1.39). Engine options you added to `"args"` by hand are not carried over: setup names
  them, and you add them again.
- **The model files** (`models/`, `packs/`, `mtp/`, 70-120 GB): in **`Strata-data` next to the Strata folder**, or
  wherever `--data-dir` put them.
- **Where that data folder is:** `%APPDATA%\Strata\settings.json` on Windows, `~/.config/strata/settings.json` on
  Linux ([details](DETAILS.md#before-you-start)).
- **The program itself:** `.venv/`, `engine/` and `third_party/` in the Strata folder.
- **Where github.com cannot be reached:** a build from source downloads llama.cpp's source (ggml, gguf-py) from
  GitHub at the commit `LLAMA_CPP_COMMIT` in `setup.py` names. Put that commit's tree in `third_party/llama.cpp`
  yourself (from a mirror or another PC) and setup uses it instead (#585).

### Keeping the models on another disk

The model files are the only big part (70 to 190 GB). Put them where there is room.

- **Pick the folder when you install:** `./setup.sh --data-dir /mnt/big/Strata-data` (Windows:
  `START-HERE.bat --data-dir D:\Strata`). The folder is remembered in `%APPDATA%\Strata\settings.json` on Windows and
  `~/.config/strata/settings.json` on Linux. A new folder never moves anything by itself: without `--move-data` the
  models you already have stay where they are and the new folder gets the new downloads; with `--move-data` (or the
  answer "move") setup moves them in, and only a move or `--set-default-data-dir` changes the remembered folder.
  Nothing on a metered or slow drive is copied twice: setup says which folders hold model files and what it will do.
- **Files you already have:** `--gguf-dir FOLDER` (or `--models-dir`) points setup at a folder of shards, a folder above
  it, or one `.gguf` file, and setup uses them in place instead of downloading. A folder that holds several sizes needs
  the one `.gguf` file named.
- **Drives that are not NTFS** (exFAT, FAT32, a network share) work: Strata writes straight into `<folder>\models` and makes no
  link there.
- **What stays with the program:** `.venv/` (Python and its packages), `engine/` and `third_party/` in the Strata
  folder, 1-3 GB; your settings, the run configs and the logs are a few MB. Nothing else is large: downloads, the
  prepared model data (`packs`) and the draft layer (`mtp`) are written in the model folder, and so are the
  half-finished files of an interrupted download.

## Setup's questions
These are the questions of the installer (`START-HERE.bat`, `./setup.sh`). Every one has a recommended answer:
press Enter for it, or take them all with `--yes`.

- **Which model and size?** The original, Swift 1.5, the Coder or Unsloth's 4-bit, and Q2_0, IQ2_XS, IQ3_XXS or
  IQ3_S - see [which model](MODELS.md).
- **How much context?** How much text it can keep in mind at once (it suggests one for your card). 384K and
  512K (experimental) extend the model past its trained 262K by rope scaling - the setup turns it on itself (yarn and a
  covering factor; `--rope-scaling`/`--rope-scale` override) ([details](DETAILS.md): "Context extension past
  262K").
- **Images?** Whether it should also read pictures. Pictures are on by default for models that can read them. The
  image encoder (0.9 GB) runs on the CPU when your card has less than 24 GB (about 3-13 s per picture, nothing taken
  from the GPU) and on the GPU from 24 GB (0.1-0.5 s per picture, ~1.4 GB of VRAM kept free for it). The rule is the
  same for NVIDIA and AMD cards; `--vision gpu` and `--vision cpu` choose the reader yourself, `--vision no` turns
  pictures off. On a Radeon AI PRO R9700 the GPU reader took 57 ms for a 260-token picture and the CPU reader 3.1 s.
  A Mac reads on its GPU (0.45 s for a 260-token picture on an M4). [Details](DETAILS.md#images-vision).
- **Experimental speed projection?** Off unless you say yes - [read what it does](DETAILS.md#experimental-speed-projection-experimental-off-by-default)
  first. It changes how the model answers, and only the original model offers it.

With `--yes` setup takes the recommended answer to every question.

## Tuning for your PC

Every PC is different: `START-HERE.bat --calibrate` (Linux: `./setup.sh --calibrate`) measures a few engine settings
on yours and keeps the fastest (about 15-30 minutes, longer on a slow card; on an RTX 5070 with a Ryzen 5 7600 it made the Coder 7% faster).
It keeps a setting only when it is more than 3% faster, and the result is remembered per PC and model, so updates
keep it. Measuring the CPU worker count needs a fresh engine, so the model is loaded more than once: the PC is
busy, and can stop responding for a minute or two, once per restart. When it finishes it **starts the model**,
so the server is already running when it returns - do not start it a second time.
NVIDIA cards for now. [What it measures](DETAILS.md#double-click-start-herebat).

## Options without questions

These are the options of the installer; `START-HERE.bat --help` and `./setup.sh --help` list them all.

```
START-HERE.bat --setup                          install another model, or change context / images
SETUP.bat                                       the same (double-click it)
START-HERE.bat --model IQ2_XS --context 32768 --vision yes --yes     no questions
START-HERE.bat --gguf-dir D:\models\IQ2_XS       use GGUF files you already have
START-HERE.bat --inspect D:\models\some.gguf     what a GGUF really holds and whether Strata runs it (no download)
START-HERE.bat --data-dir E:\Strata-data         keep the model files somewhere else
START-HERE.bat --port 8081                      another port
START-HERE.bat --gpu 1                          another GPU (setup picks the one with the most VRAM)
START-HERE.bat --gpus 0,2                       several GPUs sharing the model
START-HERE.bat --vram-reserve-mib 2048          leave 2 GB of VRAM free for other programs (remembered)
START-HERE.bat --no-browser                     do not open the chat page when the model is ready (remembered;
                                                --browser undoes it)
START-HERE.bat --setup --backend hip            the AMD engine on a PC that also has an NVIDIA card
START-HERE.bat --setup --host 0.0.0.0 --api-key <secret>     reachable from other devices, with a key
START-HERE.bat --calibrate                      tune the engine for this PC (about 15-30 minutes, longer on a slow card), then start
START-HERE.bat --check                          only check this PC
```

**Leaving VRAM for other programs (#493):** Strata fills the graphics card's free VRAM with experts (the expert cache)
and leaves `--vram-reserve-mib` MiB free: 700 by default. For a game, a 3D program or another model beside it, leave
more: `START-HERE.bat --vram-reserve-mib 2048` (Linux: `./setup.sh --vram-reserve-mib 2048`) writes it into the
model's `strata-<model>.json` and starts it; at setup (`--setup --vram-reserve-mib 2048`) it goes into the new config.
By hand: add `"--vram-reserve-mib", "2048"` to the config's `"args"` list and restart. The expert cache is then that
much smaller, so answers can be a little slower. The engine sizes its cache from the VRAM free when it starts: what
another program already holds then is left alone anyway; the reserve is room for what it takes later.

**An AMD card that also drives a Linux desktop (#560 #516):** with the default reserve the expert cache fills the
card, and when the desktop (the compositor, a browser, a new app) needs more VRAM, the amdgpu driver moves GPU memory
to system RAM, which the model's experts already fill: the OOM killer then ends the desktop session (KWin, plasmashell)
or the compositor fails ("Failed to pin framebuffer"). `./setup.sh --vram-reserve-mib 3072` fixed it in both reports
(about 2.3 GB fewer experts in VRAM, a few % of speed). Setup and the server window say so on such a PC.

**A card under 8 GB (#496):** when the default reserve leaves the expert cache too little room, the engine lowers the
reserve (down to 300 MiB) until it fits, and warns if the card then ends nearly full. If the start stops with "no VRAM
is left for the expert cache", that log line says how much is short; an 8K context and `--draft-vocab en` at setup
free the most.

**Model files downloaded by hand, or from a mirror (#495):** setup's step 5 prints the folder it expects them in
(`Strata-data\models\<SIZE>\`, e.g. `Strata-data\models\IQ3_XXS\`): put them there with their original names, or
point setup at them with `--gguf-dir`. To see what a file really holds before using or downloading it, `--inspect`
reads only its headers (a few MB, also over the network: a file, a folder, a URL, `ms:owner/repo` for ModelScope or
`hf:owner/repo`): every weight group's real bits per weight and storage types, and whether it is one of the files setup
installs (under any name), stored like one of them, or not one Strata runs (another architecture, or experts in a
format no Strata kernel reads). A name says little: Unsloth's `UD-IQ3_XXS` stores its routed experts at 3.22 bits per
weight, `UD-Q4_K_XL` at 5.10, the original `Q2_0` at 2.25 and `IQ3_S` at 3.33. To let setup download from a Hugging Face mirror itself, set `HF_ENDPOINT`
first (Windows: `set HF_ENDPOINT=https://hf-mirror.com`, Linux: `export HF_ENDPOINT=https://hf-mirror.com`): the same
pinned revisions and checks apply, and the MTP draft layer comes from there too.

**From ModelScope (mainland China):** every repository setup downloads from (the GSQ-RCO models, Swift 1.5, the
Coder, Unsloth's files, and the original checkpoint the MTP draft layer is taken from) is on
[ModelScope](https://www.modelscope.cn) under the same name, with the same files. Setup never switches to it by
itself (a download that fails says how): use `--source modelscope` (`STRATA_SOURCE=modelscope`). ModelScope serves a
repository's current files (no pinned revision), so each file is checked against the SHA-256 ModelScope publishes for
it (self-attested: a changed upstream repository would carry its own hash), and the MTP tensors against the
pinned checkpoint's own hashes, as from Hugging Face; setup says so when you choose it. Measured on a PC in mainland
China on 2026-10-05: 11-14 MB/s; the Q2_0 and IQ3_S files matched their published SHA-256, and Q2_0's shard 1 matched
the copy from hf-mirror.com.

On Linux the same options go to `./setup.sh`. `START-HERE.bat --help` lists them all. The server's own settings
(sharing the GPU with games, MCP tools, CORS, API keys, the API itself) are in the [details](DETAILS.md#using-it).
