# Git Visual History (Gource GUI)

`git_visual_history` is a `CustomTkinter` desktop launcher for visualizing a git repository with [Gource](https://github.com/acaudwell/Gource).

It keeps the same core behavior as the original script (launch Gource with preset options), but now matches the newer tools in this repo:
- GUI settings editor
- persistent `config.json`
- first-run defaults from `config_default.json`
- window size / theme persistence
- launch status + command preview

---

## Requirements

### Python

- Python 3.10+ recommended

### Python package

- `customtkinter`

Install:

```bash
pip install customtkinter
```

Or use the local bootstrap script:

```bash
python git/git_visual_history/setup.py
```

### Gource

Install Gource and ensure one of these works in your terminal:
- `gource`
- `gource.cmd`

You can also point the app at a full executable path in the GUI/config.

---

## Run

From the repo root:

```bash
python git/git_visual_history/visualize_history.py
```

The app opens a GUI where you can:
- choose the repository path
- detect/test Gource executable lookup
- edit common Gource options
- save config
- preview the generated command
- launch/terminate Gource

---

## Config Files

Files are stored beside the script:
- `git/git_visual_history/config_default.json`
- `git/git_visual_history/config.json`

Behavior:
- On first run, `config.json` is created automatically (from defaults).
- On later runs, user values in `config.json` override defaults.

### Common config fields

- `repo_path`: repository to visualize (relative to the script folder or absolute path)
- `gource_executables`: executable candidates checked in order
- `prompt_before_launch`: GUI confirmation dialog before launching Gource
- `prompt_before_close`: notify when Gource exits
- `show_controls`: prints Gource controls into the app log before launch
- `title_prefix`: prefix used for the Gource window title
- `logo_path`: logo path relative to repo root (or absolute path)
- `extra_args`: additional raw Gource args (one per line in GUI)

### `gource_options`

The GUI edits these common options:
- `fullscreen`
- `camera_mode`
- `background`
- `seconds_per_day`
- `auto_skip_seconds`
- `file_idle_time`
- `max_file_lag`
- `bloom_multiplier`
- `bloom_intensity`
- `branch_elasticity`
- `show_key`
- `highlight_users`

---

## Notes

- `color_theme` changes are persisted, but a restart may be required for full visual effect.
- `logo_path` is resolved relative to the selected repo path.
- The launcher does not bundle Gource; it only launches it.

---

## Troubleshooting

### "No suitable Gource executable found"

- Confirm Gource is installed.
- Confirm `gource` runs in a terminal.
- Add the full path to `gource.exe` in `gource_executables`.

### "Not a git repository (missing .git)"

- Set `repo_path` to a folder that contains a `.git` directory.

### `customtkinter` import error

Install the dependency:

```bash
pip install customtkinter
```
