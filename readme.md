# Git Visual History

Desktop launcher for visualizing a Git repository with [Gource](https://github.com/acaudwell/Gource).

## Requirements

- Python 3.10+
- Dependencies from `requirements.txt`

Gource is bundled for supported release platforms and is selected automatically.
If a native bundle is absent, the launcher falls back to `gource`, `gource.cmd`,
or a configured full executable path.

## Install

```bash
python setup.py --venv
```

Or manually:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On Linux or macOS, activate the virtual environment with `source .venv/bin/activate`.

## Run

```bash
python visualize-history.py
```

On first run, the app creates `config.json` from `config-default.json`.

## What The App Provides

- Repository path picker
- Gource executable detection
- Common Gource option editor
- Command preview
- Launch and terminate controls
- Persistent local config

`readme-gource.txt` is included as Gource reference documentation.

## Bundled Gource

Native payloads live under `vendor/gource/<platform>-<architecture>/`:

- `windows-x86_64/gource.exe`
- `linux-x86_64/gource.AppImage` (with `gource` accepted for unpacked builds)
- `macos-x86_64/gource`
- `macos-arm64/gource`

The checked-in payloads are native to their named operating system and
architecture. Windows x86-64 uses the official Gource 0.53 portable
distribution. Linux x86-64 uses Gource 0.56 in an AppImage that does not require
FUSE. macOS arm64 and x86-64 use relocated Gource 0.56 Homebrew binaries and
their dynamic libraries; the wrapper ad-hoc signs them locally with Apple's
built-in `codesign` before first launch. See `vendor/gource/manifest.json` for
sources, checksums, and validation state.

The launcher never tries to execute a binary for another operating system or
architecture. Windows and Linux have native smoke-test evidence. The macOS
payloads are native Mach-O arm64/x86-64 bundles with closed dependency graphs,
but remain runtime-untested until the separate macOS wishlist validation can be
run on Apple hardware.

Build and smoke-test the Linux x86-64 AppImage with Docker Desktop:

```bash
python tool/gource/package-gource.py --platform linux
```
