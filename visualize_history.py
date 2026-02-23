#!/usr/bin/env python3
# =============================================================================
# [Python Script] [CustomTkinter GUI] [Git Visual History (Gource)]
# =============================================================================
"""
CustomTkinter launcher for interactive git history visualization with Gource.

Features:
- GUI editor for common Gource options
- Config persistence (config.json beside script)
- First-run config auto-created from config_default.json
- Window size + appearance/theme persistence
- Best-effort Windows taskbar identity + window icon hooks
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any

try:
  import customtkinter as ctk
except Exception as e:
  raise SystemExit(
    "\n".join([
      "Missing dependency: customtkinter",
      "",
      "Install:",
      "  pip install customtkinter",
      "",
      f"Original error: {e}",
    ])
  )


APP_TITLE = "Git Visual History - Cure Interactive"
APP_USER_MODEL_ID = "CureInteractive.GitVisualHistory"

PATH_DIR_SCRIPT = os.path.abspath(os.path.dirname(__file__))
PATH_CONFIG_JSON = os.path.join(PATH_DIR_SCRIPT, "config.json")
PATH_CONFIG_DEFAULT_JSON = os.path.join(PATH_DIR_SCRIPT, "config_default.json")

GOURCE_CONTROLS_TEXT = """
Gource Controls:

  (SPACE) Pause/resume                   (LEFT-MOUSE) Manually control camera
  (RIGHT-MOUSE) Rotate camera            (V or MIDDLE-MOUSE) Toggle camera mode
  (C)   Displays Gource logo             (K)   Toggle file extension key
  (M)   Toggle mouse visibility          (N)   Jump to next log entry
  (S)   Randomize colours                (D)   Cycle directory name mode
  (F)   Cycle file name mode             (U)   Cycle user name mode
  (G)   Toggle users display             (T)   Toggle directory tree edges
  (R)   Toggle root directory edges      (+ -) Adjust simulation speed
  (< >) Adjust time scale                (TAB) Cycle visible users
  (F12) Screenshot                       (Alt+Enter) Fullscreen toggle
  (ESC) Quit

 * Camera modes: Track activity / show entire tree

 * While paused you may use the mouse to inspect the detail of individual files
   and users.
""".strip("\n")

DEFAULT_CONFIG: dict[str, Any] = {
  "window": {
    "width": 980,
    "height": 760,
  },
  "appearance_mode": "System",
  "color_theme": "blue",
  "repo_path": "../../",
  "gource_executables": ["gource", "gource.cmd"],
  "prompt_before_launch": True,
  "prompt_before_close": False,
  "show_controls": True,
  "title_prefix": "Interactive Commit History: ",
  "logo_path": "Scripts/VisualizeHistory/Graphic.png",
  "extra_args": [],
  "gource_options": {
    "fullscreen": True,
    "camera_mode": "overview",
    "background": "111111",
    "seconds_per_day": "24",
    "auto_skip_seconds": "1",
    "file_idle_time": "0",
    "max_file_lag": "1",
    "bloom_multiplier": "0.5",
    "bloom_intensity": "0.5",
    "branch_elasticity": "0.0001",
    "show_key": True,
    "highlight_users": True,
  },
}


# =============================================================================
# Helpers
# =============================================================================

def _read_json(path: str) -> dict[str, Any] | None:
  try:
    if not os.path.isfile(path):
      return None
    with open(path, "r", encoding="utf-8") as f:
      data = json.load(f)
    return data if isinstance(data, dict) else None
  except Exception:
    return None


def _write_json_atomic(path: str, data: dict[str, Any]) -> None:
  tmp = path + ".tmp"
  with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
  os.replace(tmp, path)


def _deep_copy_json_dict(data: dict[str, Any]) -> dict[str, Any]:
  return json.loads(json.dumps(data))


def _deep_merge_dict(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
  out = _deep_copy_json_dict(base)
  for key, value in overlay.items():
    if isinstance(value, dict) and isinstance(out.get(key), dict):
      out[key] = _deep_merge_dict(out[key], value)
    else:
      out[key] = value
  return out


def load_or_create_config() -> dict[str, Any]:
  template = _read_json(PATH_CONFIG_DEFAULT_JSON)
  if not isinstance(template, dict):
    template = _deep_copy_json_dict(DEFAULT_CONFIG)
  user_cfg = _read_json(PATH_CONFIG_JSON)
  if isinstance(user_cfg, dict):
    return _deep_merge_dict(template, user_cfg)
  _write_json_atomic(PATH_CONFIG_JSON, template)
  return _deep_copy_json_dict(template)


def set_windows_app_user_model_id(app_id: str) -> None:
  try:
    if os.name != "nt":
      return
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(str(app_id))
  except Exception:
    return


def set_window_icon(root, ico_path: str, png_path: str) -> None:
  ico_abs = os.path.abspath(ico_path) if ico_path else ""
  png_abs = os.path.abspath(png_path) if png_path else ""
  try:
    if ico_abs and os.path.isfile(ico_abs):
      root.iconbitmap(ico_abs)
  except Exception:
    pass
  try:
    if png_abs and os.path.isfile(png_abs):
      img = tk.PhotoImage(file=png_abs)
      root.iconphoto(True, img)
      root._iconphoto_ref = img
  except Exception:
    pass


def _resolve_path_from_script(path_value: str) -> str:
  if not path_value:
    return ""
  if os.path.isabs(path_value):
    return os.path.abspath(path_value)
  return os.path.abspath(os.path.join(PATH_DIR_SCRIPT, path_value))


def _resolve_path_from_repo(repo_path: str, path_value: str) -> str:
  if not path_value:
    return ""
  if os.path.isabs(path_value):
    return os.path.abspath(path_value)
  return os.path.abspath(os.path.join(repo_path, path_value))


def find_gource_executable(candidates: list[str]) -> str | None:
  for candidate in candidates:
    c = str(candidate or "").strip()
    if not c:
      continue
    if os.path.isabs(c) and os.path.isfile(c):
      return c
    found = shutil.which(c)
    if found:
      return found
  return None


def build_gource_command(
  gource_executable: str,
  repo_path: str,
  project_name: str,
  config: dict[str, Any],
) -> list[str]:
  options = config.get("gource_options", {})
  if not isinstance(options, dict):
    options = {}

  title_prefix = str(config.get("title_prefix", "Interactive Commit History: ") or "")
  title = f"{title_prefix}{project_name}" if project_name else title_prefix.rstrip()

  cmd: list[str] = [gource_executable]
  cmd.append("-f" if bool(options.get("fullscreen", True)) else "-w")
  cmd.extend(["--title", title])
  cmd.extend(["--camera-mode", str(options.get("camera_mode", "overview"))])
  cmd.extend(["--background", str(options.get("background", "111111"))])
  cmd.extend(["--seconds-per-day", str(options.get("seconds_per_day", "24"))])
  cmd.extend(["--auto-skip-seconds", str(options.get("auto_skip_seconds", "1"))])
  cmd.extend(["--file-idle-time", str(options.get("file_idle_time", "0"))])
  cmd.extend(["--max-file-lag", str(options.get("max_file_lag", "1"))])
  if bool(options.get("show_key", True)):
    cmd.append("--key")
  cmd.extend(["--bloom-multiplier", str(options.get("bloom_multiplier", "0.5"))])
  cmd.extend(["--bloom-intensity", str(options.get("bloom_intensity", "0.5"))])
  cmd.extend(["-e", str(options.get("branch_elasticity", "0.0001"))])
  if bool(options.get("highlight_users", True)):
    cmd.append("--highlight-users")

  logo_path_raw = str(config.get("logo_path", "") or "").strip()
  if logo_path_raw:
    logo_path = _resolve_path_from_repo(repo_path, logo_path_raw)
    if os.path.isfile(logo_path):
      cmd.extend(["--logo", logo_path])

  extra_args = config.get("extra_args", [])
  if isinstance(extra_args, list):
    cmd.extend([str(x) for x in extra_args if str(x).strip()])

  return cmd


def _split_csv_list(value: str) -> list[str]:
  return [part.strip() for part in value.split(",") if part.strip()]


def _split_lines_list(value: str) -> list[str]:
  return [line.strip() for line in value.splitlines() if line.strip()]


# =============================================================================
# GUI App
# =============================================================================

class GitVisualHistoryApp(ctk.CTk):
  def __init__(self):
    super().__init__()

    self.config_data = load_or_create_config()

    ctk.set_appearance_mode(str(self.config_data.get("appearance_mode", "System")))
    ctk.set_default_color_theme(str(self.config_data.get("color_theme", "blue")))

    w = int(self.config_data.get("window", {}).get("width", 980))
    h = int(self.config_data.get("window", {}).get("height", 760))

    self.title(APP_TITLE)
    self.geometry(f"{w}x{h}")
    self.minsize(900, 680)

    set_window_icon(
      self,
      os.path.join(PATH_DIR_SCRIPT, "icon.ico"),
      os.path.join(PATH_DIR_SCRIPT, "icon.png"),
    )

    self._proc_lock = threading.Lock()
    self._gource_process: subprocess.Popen | None = None
    self._watcher_thread: threading.Thread | None = None

    self.var_repo_path = tk.StringVar(value=str(self.config_data.get("repo_path", "../../")))
    self.var_gource_execs = tk.StringVar(value=", ".join(self.config_data.get("gource_executables", ["gource", "gource.cmd"])))
    self.var_title_prefix = tk.StringVar(value=str(self.config_data.get("title_prefix", "Interactive Commit History: ")))
    self.var_logo_path = tk.StringVar(value=str(self.config_data.get("logo_path", "")))
    self.var_appearance_mode = tk.StringVar(value=str(self.config_data.get("appearance_mode", "System")))
    self.var_color_theme = tk.StringVar(value=str(self.config_data.get("color_theme", "blue")))
    self.var_prompt_before_launch = tk.BooleanVar(value=bool(self.config_data.get("prompt_before_launch", True)))
    self.var_prompt_before_close = tk.BooleanVar(value=bool(self.config_data.get("prompt_before_close", False)))
    self.var_show_controls = tk.BooleanVar(value=bool(self.config_data.get("show_controls", True)))

    g = self.config_data.get("gource_options", {})
    if not isinstance(g, dict):
      g = {}
    self.var_fullscreen = tk.BooleanVar(value=bool(g.get("fullscreen", True)))
    self.var_camera_mode = tk.StringVar(value=str(g.get("camera_mode", "overview")))
    self.var_background = tk.StringVar(value=str(g.get("background", "111111")))
    self.var_seconds_per_day = tk.StringVar(value=str(g.get("seconds_per_day", "24")))
    self.var_auto_skip_seconds = tk.StringVar(value=str(g.get("auto_skip_seconds", "1")))
    self.var_file_idle_time = tk.StringVar(value=str(g.get("file_idle_time", "0")))
    self.var_max_file_lag = tk.StringVar(value=str(g.get("max_file_lag", "1")))
    self.var_bloom_multiplier = tk.StringVar(value=str(g.get("bloom_multiplier", "0.5")))
    self.var_bloom_intensity = tk.StringVar(value=str(g.get("bloom_intensity", "0.5")))
    self.var_branch_elasticity = tk.StringVar(value=str(g.get("branch_elasticity", "0.0001")))
    self.var_show_key = tk.BooleanVar(value=bool(g.get("show_key", True)))
    self.var_highlight_users = tk.BooleanVar(value=bool(g.get("highlight_users", True)))

    self._build_ui()

    extra_args = self.config_data.get("extra_args", [])
    if isinstance(extra_args, list):
      self.text_extra_args.insert("1.0", "\n".join(str(x) for x in extra_args if str(x).strip()))

    self.protocol("WM_DELETE_WINDOW", self._on_close)
    self.after(750, self._poll_process_state)
    self._log("App started.")

  def _build_ui(self) -> None:
    self.grid_columnconfigure(0, weight=1)
    self.grid_rowconfigure(1, weight=1)
    self.grid_rowconfigure(2, weight=1)

    top = ctk.CTkFrame(self)
    top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
    top.grid_columnconfigure(1, weight=1)
    top.grid_columnconfigure(4, weight=1)

    ctk.CTkLabel(top, text="Repo").grid(row=0, column=0, sticky="w", padx=(10, 6), pady=8)
    self.entry_repo = ctk.CTkEntry(top, textvariable=self.var_repo_path)
    self.entry_repo.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=8)
    ctk.CTkButton(top, text="Browse", width=90, command=self._choose_repo).grid(row=0, column=2, padx=(0, 10), pady=8)

    ctk.CTkLabel(top, text="Gource").grid(row=1, column=0, sticky="w", padx=(10, 6), pady=8)
    self.entry_execs = ctk.CTkEntry(top, textvariable=self.var_gource_execs)
    self.entry_execs.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=8)
    ctk.CTkButton(top, text="Detect", width=90, command=self._detect_gource).grid(row=1, column=2, padx=(0, 10), pady=8)

    ctk.CTkLabel(top, text="Title Prefix").grid(row=0, column=3, sticky="w", padx=(10, 6), pady=8)
    ctk.CTkEntry(top, textvariable=self.var_title_prefix).grid(row=0, column=4, sticky="ew", padx=(0, 10), pady=8)
    ctk.CTkLabel(top, text="Logo Path").grid(row=1, column=3, sticky="w", padx=(10, 6), pady=8)
    ctk.CTkEntry(top, textvariable=self.var_logo_path).grid(row=1, column=4, sticky="ew", padx=(0, 10), pady=8)

    middle = ctk.CTkFrame(self)
    middle.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
    for col in range(4):
      middle.grid_columnconfigure(col, weight=1)

    row = 0
    ctk.CTkLabel(middle, text="Appearance").grid(row=row, column=0, sticky="w", padx=10, pady=(10, 6))
    ctk.CTkOptionMenu(
      middle,
      variable=self.var_appearance_mode,
      values=["System", "Light", "Dark"],
      command=self._on_change_appearance_mode,
    ).grid(row=row, column=1, sticky="ew", padx=(0, 10), pady=(10, 6))
    ctk.CTkLabel(middle, text="Color Theme").grid(row=row, column=2, sticky="w", padx=10, pady=(10, 6))
    ctk.CTkOptionMenu(
      middle,
      variable=self.var_color_theme,
      values=["blue", "green", "dark-blue"],
      command=self._on_change_color_theme,
    ).grid(row=row, column=3, sticky="ew", padx=(0, 10), pady=(10, 6))

    row += 1
    ctk.CTkCheckBox(middle, text="Fullscreen", variable=self.var_fullscreen).grid(row=row, column=0, sticky="w", padx=10, pady=6)
    ctk.CTkCheckBox(middle, text="Show extension key", variable=self.var_show_key).grid(row=row, column=1, sticky="w", padx=10, pady=6)
    ctk.CTkCheckBox(middle, text="Highlight users", variable=self.var_highlight_users).grid(row=row, column=2, sticky="w", padx=10, pady=6)
    ctk.CTkOptionMenu(middle, variable=self.var_camera_mode, values=["overview", "track"]).grid(row=row, column=3, sticky="ew", padx=(10, 10), pady=6)

    row += 1
    ctk.CTkCheckBox(middle, text="Show controls before launch", variable=self.var_show_controls).grid(row=row, column=0, sticky="w", padx=10, pady=6)
    ctk.CTkCheckBox(middle, text="Confirm before launch", variable=self.var_prompt_before_launch).grid(row=row, column=1, sticky="w", padx=10, pady=6)
    ctk.CTkCheckBox(middle, text="Notify after exit", variable=self.var_prompt_before_close).grid(row=row, column=2, sticky="w", padx=10, pady=6)

    row += 1
    self._labeled_entry(middle, row, 0, "Background", self.var_background)
    self._labeled_entry(middle, row, 1, "Seconds/Day", self.var_seconds_per_day)
    self._labeled_entry(middle, row, 2, "Auto Skip", self.var_auto_skip_seconds)
    self._labeled_entry(middle, row, 3, "File Idle", self.var_file_idle_time)

    row += 1
    self._labeled_entry(middle, row, 0, "Max File Lag", self.var_max_file_lag)
    self._labeled_entry(middle, row, 1, "Bloom Mult", self.var_bloom_multiplier)
    self._labeled_entry(middle, row, 2, "Bloom Intensity", self.var_bloom_intensity)
    self._labeled_entry(middle, row, 3, "Elasticity", self.var_branch_elasticity)

    row += 1
    ctk.CTkLabel(middle, text="Extra Args (one per line)").grid(row=row, column=0, columnspan=4, sticky="w", padx=10, pady=(8, 4))
    self.text_extra_args = ctk.CTkTextbox(middle, height=90)
    self.text_extra_args.grid(row=row + 1, column=0, columnspan=4, sticky="nsew", padx=10, pady=(0, 10))
    middle.grid_rowconfigure(row + 1, weight=1)

    bottom = ctk.CTkFrame(self)
    bottom.grid(row=2, column=0, sticky="nsew", padx=12, pady=(8, 12))
    bottom.grid_columnconfigure(0, weight=1)
    bottom.grid_rowconfigure(1, weight=1)

    actions = ctk.CTkFrame(bottom)
    actions.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 8))
    actions.grid_columnconfigure(8, weight=1)

    self.btn_launch = ctk.CTkButton(actions, text="Launch Gource", command=self._on_launch)
    self.btn_launch.grid(row=0, column=0, padx=(0, 8), pady=8)
    self.btn_stop = ctk.CTkButton(actions, text="Terminate", command=self._on_terminate, fg_color="#aa3333", hover_color="#8d2a2a")
    self.btn_stop.grid(row=0, column=1, padx=(0, 8), pady=8)
    ctk.CTkButton(actions, text="Save Config", command=self._on_save).grid(row=0, column=2, padx=(0, 8), pady=8)
    ctk.CTkButton(actions, text="Show Command", command=self._on_show_command).grid(row=0, column=3, padx=(0, 8), pady=8)
    ctk.CTkButton(actions, text="Open Repo", command=self._open_repo_folder).grid(row=0, column=4, padx=(0, 8), pady=8)

    self.lbl_status = ctk.CTkLabel(actions, text="Idle")
    self.lbl_status.grid(row=0, column=9, sticky="e", padx=(8, 0), pady=8)

    self.text_log = ctk.CTkTextbox(bottom)
    self.text_log.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
    self.text_log.configure(state="disabled")

    self._refresh_running_state()

  def _labeled_entry(self, parent, row: int, col: int, label: str, var: tk.StringVar) -> None:
    frame = ctk.CTkFrame(parent)
    frame.grid(row=row, column=col, sticky="ew", padx=10, pady=6)
    frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(frame, text=label).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 2))
    ctk.CTkEntry(frame, textvariable=var).grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))

  def _log(self, msg: str) -> None:
    line = str(msg).rstrip()
    if not line:
      return
    self.text_log.configure(state="normal")
    self.text_log.insert("end", line + "\n")
    self.text_log.see("end")
    self.text_log.configure(state="disabled")

  def _on_change_appearance_mode(self, value: str) -> None:
    try:
      ctk.set_appearance_mode(value)
      self._log(f"Appearance mode set to: {value}")
    except Exception as e:
      self._log(f"Failed to apply appearance mode: {e}")

  def _on_change_color_theme(self, value: str) -> None:
    self._log(f"Color theme change selected ({value}); restart may be required for full effect.")

  def _choose_repo(self) -> None:
    initial = self._resolve_repo_path_for_ui()
    chosen = filedialog.askdirectory(initialdir=initial if os.path.isdir(initial) else PATH_DIR_SCRIPT)
    if chosen:
      self.var_repo_path.set(os.path.relpath(chosen, PATH_DIR_SCRIPT))
      self._log(f"Repo path set to: {self.var_repo_path.get()}")

  def _detect_gource(self) -> None:
    candidates = _split_csv_list(self.var_gource_execs.get())
    found = find_gource_executable(candidates)
    if found:
      self._log(f"Gource found: {found}")
    else:
      self._log(f"Gource not found. Tried: {candidates or ['gource', 'gource.cmd']}")

  def _resolve_repo_path_for_ui(self) -> str:
    return _resolve_path_from_script(self.var_repo_path.get().strip())

  def _collect_config_from_ui(self) -> dict[str, Any]:
    cfg = _deep_copy_json_dict(DEFAULT_CONFIG)
    cfg["window"]["width"] = max(self.winfo_width(), 900)
    cfg["window"]["height"] = max(self.winfo_height(), 680)
    cfg["appearance_mode"] = self.var_appearance_mode.get().strip() or "System"
    cfg["color_theme"] = self.var_color_theme.get().strip() or "blue"
    cfg["repo_path"] = self.var_repo_path.get().strip() or "../../"
    cfg["gource_executables"] = _split_csv_list(self.var_gource_execs.get()) or ["gource", "gource.cmd"]
    cfg["prompt_before_launch"] = bool(self.var_prompt_before_launch.get())
    cfg["prompt_before_close"] = bool(self.var_prompt_before_close.get())
    cfg["show_controls"] = bool(self.var_show_controls.get())
    cfg["title_prefix"] = self.var_title_prefix.get()
    cfg["logo_path"] = self.var_logo_path.get().strip()
    cfg["extra_args"] = _split_lines_list(self.text_extra_args.get("1.0", "end"))

    go = cfg["gource_options"]
    go["fullscreen"] = bool(self.var_fullscreen.get())
    go["camera_mode"] = self.var_camera_mode.get().strip() or "overview"
    go["background"] = self.var_background.get().strip() or "111111"
    go["seconds_per_day"] = self.var_seconds_per_day.get().strip() or "24"
    go["auto_skip_seconds"] = self.var_auto_skip_seconds.get().strip() or "1"
    go["file_idle_time"] = self.var_file_idle_time.get().strip() or "0"
    go["max_file_lag"] = self.var_max_file_lag.get().strip() or "1"
    go["bloom_multiplier"] = self.var_bloom_multiplier.get().strip() or "0.5"
    go["bloom_intensity"] = self.var_bloom_intensity.get().strip() or "0.5"
    go["branch_elasticity"] = self.var_branch_elasticity.get().strip() or "0.0001"
    go["show_key"] = bool(self.var_show_key.get())
    go["highlight_users"] = bool(self.var_highlight_users.get())
    return cfg

  def _save_config(self) -> None:
    self.config_data = self._collect_config_from_ui()
    _write_json_atomic(PATH_CONFIG_JSON, self.config_data)

  def _on_save(self) -> None:
    try:
      self._save_config()
      self._log(f"Saved config: {PATH_CONFIG_JSON}")
    except Exception as e:
      messagebox.showerror(APP_TITLE, f"Failed to save config:\n{e}")

  def _build_launch_context(self) -> tuple[dict[str, Any], str, str, list[str]]:
    cfg = self._collect_config_from_ui()
    repo_path = _resolve_path_from_script(str(cfg.get("repo_path", "../../")))
    if not os.path.isdir(repo_path):
      raise ValueError(f"Repository path does not exist:\n{repo_path}")
    if not os.path.isdir(os.path.join(repo_path, ".git")):
      raise ValueError(f"Not a git repository (missing .git):\n{repo_path}")

    candidates = cfg.get("gource_executables", ["gource", "gource.cmd"])
    if not isinstance(candidates, list):
      candidates = ["gource", "gource.cmd"]
    gource_exe = find_gource_executable([str(x) for x in candidates])
    if not gource_exe:
      raise ValueError(f"No suitable Gource executable found. Tried: {candidates}")

    project_name = os.path.basename(os.path.normpath(repo_path))
    cmd = build_gource_command(gource_exe, repo_path, project_name, cfg)
    return cfg, repo_path, project_name, cmd

  def _on_show_command(self) -> None:
    try:
      _, _, _, cmd = self._build_launch_context()
      self._log("Command preview:")
      self._log(" ".join(f'"{x}"' if " " in x else x for x in cmd))
    except Exception as e:
      messagebox.showerror(APP_TITLE, str(e))

  def _open_repo_folder(self) -> None:
    repo_path = self._resolve_repo_path_for_ui()
    if not os.path.isdir(repo_path):
      messagebox.showerror(APP_TITLE, f"Repo path does not exist:\n{repo_path}")
      return
    try:
      os.startfile(repo_path)  # type: ignore[attr-defined]
    except Exception:
      self._log(f"Open repo folder manually: {repo_path}")

  def _on_launch(self) -> None:
    with self._proc_lock:
      if self._gource_process and self._gource_process.poll() is None:
        messagebox.showinfo(APP_TITLE, "Gource is already running.")
        return

    try:
      cfg, repo_path, project_name, cmd = self._build_launch_context()
    except Exception as e:
      messagebox.showerror(APP_TITLE, str(e))
      return

    if bool(cfg.get("show_controls", True)):
      self._log("")
      for line in GOURCE_CONTROLS_TEXT.splitlines():
        self._log(line)

    if bool(cfg.get("prompt_before_launch", True)):
      ok = messagebox.askokcancel(
        APP_TITLE,
        f'Launch Gource for "{project_name}"?\n\nRepo:\n{repo_path}',
      )
      if not ok:
        self._log("Launch cancelled.")
        return

    try:
      self.config_data = cfg
      _write_json_atomic(PATH_CONFIG_JSON, cfg)
    except Exception as e:
      self._log(f"Warning: failed to save config before launch: {e}")

    try:
      proc = subprocess.Popen(cmd, cwd=repo_path)
    except FileNotFoundError:
      messagebox.showerror(APP_TITLE, f"Gource executable not found:\n{cmd[0]}")
      return
    except Exception as e:
      messagebox.showerror(APP_TITLE, f"Failed to launch Gource:\n{e}")
      return

    with self._proc_lock:
      self._gource_process = proc

    self._log(f'Launched Gource for "{project_name}" (pid={proc.pid})')
    self._refresh_running_state()

    self._watcher_thread = threading.Thread(target=self._wait_for_process, daemon=True)
    self._watcher_thread.start()

  def _wait_for_process(self) -> None:
    proc: subprocess.Popen | None
    with self._proc_lock:
      proc = self._gource_process
    if not proc:
      return
    try:
      rc = proc.wait()
    except Exception as e:
      self.after(0, lambda: self._on_process_finished(-999, f"wait failed: {e}"))
      return
    self.after(0, lambda: self._on_process_finished(int(rc), None))

  def _on_process_finished(self, returncode: int, error_text: str | None) -> None:
    with self._proc_lock:
      self._gource_process = None
    if error_text:
      self._log(f"Gource watcher error: {error_text}")
    else:
      self._log(f"Gource exited with code {returncode}")
    self._refresh_running_state()
    if bool(self.var_prompt_before_close.get()):
      try:
        messagebox.showinfo(APP_TITLE, f"Gource exited with code {returncode}")
      except Exception:
        pass

  def _on_terminate(self) -> None:
    with self._proc_lock:
      proc = self._gource_process
    if not proc or proc.poll() is not None:
      self._log("No running Gource process.")
      self._refresh_running_state()
      return
    try:
      proc.terminate()
      self._log("Terminate signal sent to Gource.")
    except Exception as e:
      self._log(f"Failed to terminate Gource: {e}")

  def _poll_process_state(self) -> None:
    self._refresh_running_state()
    self.after(750, self._poll_process_state)

  def _refresh_running_state(self) -> None:
    running = False
    pid = None
    with self._proc_lock:
      if self._gource_process and self._gource_process.poll() is None:
        running = True
        pid = self._gource_process.pid
    self.btn_launch.configure(state="disabled" if running else "normal")
    self.btn_stop.configure(state="normal" if running else "disabled")
    self.lbl_status.configure(text=f"Running (pid={pid})" if running else "Idle")

  def _on_close(self) -> None:
    try:
      self._save_config()
    except Exception as e:
      self._log(f"Failed to save config on close: {e}")

    with self._proc_lock:
      proc = self._gource_process

    if proc and proc.poll() is None:
      if not messagebox.askyesno(APP_TITLE, "Gource is still running. Close launcher anyway?"):
        return

    self.destroy()


def main() -> int:
  set_windows_app_user_model_id(APP_USER_MODEL_ID)
  app = GitVisualHistoryApp()
  app.mainloop()
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
