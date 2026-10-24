# AGENTS.md

Strata runs the Qwen3.8-Flash-Next mixture-of-experts model (and its Coder, Swift 1.5, Unsloth, Gyro and NVFP4
variants, and Qwen3.6-35B-A3B) on a normal PC: one NVIDIA or AMD graphics card plus system RAM on Windows or Linux,
or an Apple Silicon Mac. Version 0.2.3, engine 0.1.48. It has two parts:

- **The engine and the server**: `src/`, `include/`, `metal/`, `sycl/` are the C++/CUDA/HIP/SYCL/Metal engine, and
  `serve/` is the Python server in front of it, with an OpenAI- and Anthropic-compatible API and a web page.
  Agents work here.
- **The installer**: `setup.py`, started by `START-HERE.bat` or `setup.sh`. It checks the PC, compiles the engine
  for the card, downloads the model, writes a run config (`strata-<model>.json`) and starts the server.
  `strata_control/` holds the rules the installer and the server share: what fits on this PC, which draft method
  to use, how a run config is written and what one may contain, and which process a start owns.

## Installing Strata for a user

1. Clone the repository and run it without questions. The first run installs what it needs, downloads the model
   (tens of GB) and the engine for this card, and starts serving; a later run just starts it.

   ```sh
   ./setup.sh --yes                    # Linux and Mac
   START-HERE.bat --yes                # Windows
   ```

   It prints the addresses when the model is up. Everything it decided - model, context, vision, parallel slots,
   engine flags - is in `strata-<model>.json`, and starting that same setup again is:

   ```sh
   .venv/bin/python serve/server.py --engine strata --config strata-q2_0.json --port 8080
   ```

   The server reads the config when it starts, so a change lands on the next start. The web page's Settings view
   edits the documented keys and leaves the rest of the file alone.

2. Keep the server on `127.0.0.1` unless the user asks for more. Beyond it an API key is recommended:
   `--api-key` (or `STRATA_API_KEY`, or `"api_key"` in the run config) sets one, and `--no-api-key` serves without
   a key - a warning, never a refusal.

## Working on the code

- How the engine works, every measured number, the API and all settings: [docs/DETAILS.md](docs/DETAILS.md) and
  the [paper](docs/paper/Strata-Paper.pdf).
- AMD (HIP) build and validation: [docs/AMD_HIP.md](docs/AMD_HIP.md); multi-GPU: [docs/MULTI_GPU.md](docs/MULTI_GPU.md);
  Mac (Metal): [docs/MAC.md](docs/MAC.md).
- Tests: the server's Python tests run without a model - `python -m unittest discover -s serve -t .`. The engine's
  tests are C++ targets built with the engine (`<name>_test`, `STRATA_BUILD_TESTS=ON`); the tuning and revision
  tests are under `tests/`. Setup's own tests run without a GPU or downloads:
  `python tools/test_setup_<name>.py` (for example `tools/test_setup_amd.py`, `tools/test_setup_choices.py`).
- Keep the docs' style: plain words, short sentences, written for non-technical users first. Give measured numbers
  with what they were measured on. Make no claim without a measurement.

## Contributing a change or report

This checkout is a personal copy of Strata: work lands in `origin` and stays there. Do not open an issue or a
pull request from here and do not suggest upstreaming one — reports and changes belong to the original project,
[Niko1221/Strata](https://github.com/Niko1221/Strata) ([CONTRIBUTING.md](CONTRIBUTING.md)).
