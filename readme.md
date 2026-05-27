# Git Visual History

Desktop launcher for visualizing a Git repository with [Gource](https://github.com/acaudwell/Gource).

## Requirements

- Python 3.10+
- Gource installed and available as `gource` or `gource.cmd`, or configured with a full executable path
- Dependencies from `requirements.txt`

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
python visualize_history.py
```

On first run, the app creates `config.json` from `config_default.json`.

## What The App Provides

- Repository path picker
- Gource executable detection
- Common Gource option editor
- Command preview
- Launch and terminate controls
- Persistent local config

`readme_gource.txt` is included as Gource reference documentation.
