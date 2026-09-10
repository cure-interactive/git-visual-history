#!/usr/bin/env python3
# =============================================================================
# [Python Script] [CustomTkinter GUI] [Git Visual History (Gource)]
# =============================================================================
"""
CustomTkinter launcher for interactive git history visualization with Gource.

Features:
- GUI editor for common Gource options
- Config persistence (config.json beside script)
- First-run config auto-created from config-default.json
- Window size + appearance/theme persistence
- Best-effort Windows taskbar identity + window icon hooks
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox
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

try:
  from PIL import Image  # type: ignore
except Exception:
  Image = None  # type: ignore


APP_TITLE = "Git Visual History - Cure Interactive"
APP_USER_MODEL_ID = "CureInteractive.GitVisualHistory"
MONOSPACE_FONT_FAMILY = "Consolas"

PATH_DIR_SCRIPT = os.path.abspath(os.path.dirname(__file__))
PATH_CONFIG_JSON = os.path.join(PATH_DIR_SCRIPT, "config.json")
PATH_CONFIG_DEFAULT_JSON = os.path.join(PATH_DIR_SCRIPT, "config-default.json")
REPO_GOURCE_CONFIG_FILENAME = ".gource.json"


def bundled_gource_candidates() -> list[str]:
  """Return native bundled Gource launchers in preference order."""
  if sys.platform == "win32":
    relative_paths = [
      ("vendor", "gource", "windows-x86_64", "gource.exe"),
    ]
  elif sys.platform == "darwin":
    machine = os.uname().machine.lower()
    architecture = "arm64" if machine in {"arm64", "aarch64"} else "x86_64"
    relative_paths = [
      ("vendor", "gource", f"macos-{architecture}", "gource"),
    ]
  else:
    machine = os.uname().machine.lower()
    architecture = "arm64" if machine in {"arm64", "aarch64"} else "x86_64"
    relative_paths = [
      ("vendor", "gource", f"linux-{architecture}", "gource.AppImage"),
      ("vendor", "gource", f"linux-{architecture}", "gource"),
    ]
  return [os.path.join(PATH_DIR_SCRIPT, *parts) for parts in relative_paths]


def _ensure_executable(path: str) -> bool:
  if not os.path.isfile(path):
    return False
  if os.name != "nt" and not os.access(path, os.X_OK):
    try:
      mode = os.stat(path).st_mode
      os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
      return False
  return True


def _dialog_title(label: str) -> str:
  label_clean = str(label or "").strip()
  if not label_clean:
    return APP_TITLE
  if label_clean.startswith(f"{APP_TITLE} - "):
    return label_clean
  return f"{APP_TITLE} - {label_clean}"

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
  "repo_path": os.path.abspath(os.path.join(PATH_DIR_SCRIPT, "../../")),
  "recent_repo_paths_max": 16,
  "recent_repo_paths": [],
  "gource_executables": ["gource", "gource.cmd"],
  "prompt_before_launch": True,
  "prompt_before_close": False,
  "title_prefix": "Interactive Commit History: ",
  "logo_path": "",
  "extra_args": [],
  "gource_options": {
    "fullscreen": False,
    "camera_mode": "overview",
    "background": "111111",
    "seconds_per_day": "3",
    "auto_skip_seconds": "1",
    "file_idle_time": "0",
    "max_file_lag": "1",
    "bloom_multiplier": "0",
    "bloom_intensity": "0",
    "branch_elasticity": "0.0001",
    "show_key": True,
    "highlight_users": False,
  },
}

DEFAULT_REPO_GOURCE_CONFIG: dict[str, Any] = {
  "title_prefix": DEFAULT_CONFIG["title_prefix"],
  "logo_path": DEFAULT_CONFIG["logo_path"],
  "extra_args": [],
  "gource_options": {},
}

DEFAULT_LAUNCHER_CONFIG: dict[str, Any] = {
  "window": {
    "width": DEFAULT_CONFIG["window"]["width"],
    "height": DEFAULT_CONFIG["window"]["height"],
  },
  "appearance_mode": DEFAULT_CONFIG["appearance_mode"],
  "color_theme": DEFAULT_CONFIG["color_theme"],
  "repo_path": DEFAULT_CONFIG["repo_path"],
  "recent_repo_paths_max": DEFAULT_CONFIG["recent_repo_paths_max"],
  "recent_repo_paths": [],
  "gource_executables": list(DEFAULT_CONFIG["gource_executables"]),
  "prompt_before_launch": DEFAULT_CONFIG["prompt_before_launch"],
  "prompt_before_close": DEFAULT_CONFIG["prompt_before_close"],
}

GOURCE_HIDE_DISPLAY_ELEMENTS: list[tuple[str, str, str]] = [
  ("bloom", "Bloom", "Hide the bloom post-processing effect."),
  ("date", "Date", "Hide the current timeline date text."),
  ("dirnames", "Directory Names", "Hide directory name labels."),
  ("files", "Files", "Hide file icons in the tree."),
  ("filenames", "Filenames", "Hide file name labels."),
  ("mouse", "Mouse", "Hide the mouse cursor inside Gource."),
  ("progress", "Progress", "Hide the progress bar widget."),
  ("root", "Root", "Hide the repository root directory node."),
  ("tree", "Tree", "Hide the animated tree structure."),
  ("users", "Users", "Hide user avatars."),
  ("usernames", "Usernames", "Hide user name labels."),
]

GOURCE_OPTION_TABS: list[str] = [
  "Timeline",
  "Window",
  "Scene",
  "Labels",
  "Users",
  "Filters",
  "Output",
]

GOURCE_OPTION_DESCRIPTIONS: dict[str, str] = {
  "fullscreen": "Run Gource in fullscreen instead of windowed mode.",
  "viewport": "Viewport size as WIDTHxHEIGHT. Add ! to make the window non-resizable.",
  "screen": "Screen index to display on when multiple monitors are available.",
  "high_dpi": "Request a high-DPI display when the window is created.",
  "window_position": "Initial window position.",
  "frameless": "Remove the native window frame and borders.",
  "transparent": "Use a transparent window background where supported.",
  "disable_input": "Disable keyboard and mouse input inside the Gource window.",
  "start_date": "Skip log entries before this date or timestamp.",
  "stop_date": "Stop reading log entries after this date or timestamp.",
  "start_position": "Start from a percentage or timestamp position in the log.",
  "stop_position": "Stop at a percentage or timestamp position in the log.",
  "stop_at_time": "Stop playback at a specific simulation time.",
  "stop_at_end": "Stop when the log reaches the end instead of continuing.",
  "loop": "Restart playback automatically after reaching the end.",
  "loop_delay_seconds": "Delay before restarting when loop mode is enabled.",
  "auto_skip_seconds": "Skip quiet periods longer than this many seconds.",
  "seconds_per_day": "How many playback seconds each day of history should take.",
  "realtime": "Play the log in real time instead of compressed timeline speed.",
  "no_time_travel": "Prevent rewinding the camera when timestamps move backward.",
  "author_time": "Use author timestamps rather than commit timestamps when available.",
  "time_scale": "Additional multiplier applied to playback speed.",
  "file_idle_time": "How long files stay visible before they disappear. 0 means no limit.",
  "file_idle_time_at_end": "How long files stay visible after playback reaches the end.",
  "camera_mode": "Use overview or track camera behavior.",
  "crop": "Crop the view on the vertical or horizontal axis.",
  "padding": "Extra padding around the camera view. Leave blank to use Gource's default.",
  "multi_sampling": "Enable multi-sampling anti-aliasing.",
  "no_vsync": "Disable vertical sync.",
  "background": "Background color in hex without the # prefix.",
  "background_image": "Path to a background image shown behind the scene.",
  "bloom_multiplier": "Bloom amount. Set to 0 to disable bloom via --hide bloom.",
  "bloom_intensity": "Brightness intensity of the bloom effect when enabled.",
  "max_files": "Maximum files to keep visible. 0 means no limit.",
  "max_file_lag": "Maximum time a commit's files can take to appear. -1 means no limit.",
  "max_user_speed": "Maximum movement speed for users per second.",
  "user_friction": "How quickly users slow down after moving.",
  "user_scale": "Scale factor for user avatars.",
  "branch_elasticity": "Elasticity of the tree nodes and branches.",
  "disable_auto_rotate": "Stop the camera from automatically rotating.",
  "hash_seed": "Seed value used by Gource's hash function.",
  "title": "Override the generated title text shown in the scene.",
  "font_file": "Font file to use for on-screen text.",
  "font_scale": "Scale all font sizes together.",
  "font_size": "Base font size for the date and title.",
  "file_font_size": "Font size for file name labels.",
  "dir_font_size": "Font size for directory labels.",
  "user_font_size": "Font size for user name labels.",
  "font_colour": "Text color for the date and title in hex.",
  "date_format": "strftime-style date format string for the displayed date.",
  "logo_offset": "Offset the logo position by XxY.",
  "show_key": "Show the file extension key legend.",
  "caption_file": "Caption file to display timed captions during playback.",
  "caption_size": "Font size used for captions.",
  "caption_colour": "Caption color in hex.",
  "caption_duration": "How long each caption remains visible.",
  "caption_offset": "Horizontal caption offset. 0 centers captions.",
  "filename_colour": "Color for file name labels in hex.",
  "dir_colour": "Color for directory labels in hex.",
  "dir_name_depth": "How deep directory names should be shown in the tree.",
  "dir_name_position": "Where directory names are drawn relative to branches.",
  "filename_time": "How long file name labels remain visible.",
  "file_extensions": "Show file extensions instead of full file names.",
  "file_extension_fallback": "Fallback to extensions when a full name is unavailable.",
  "follow_user": "Automatically follow a specific user with the camera.",
  "highlight_dirs": "Highlight all directory names.",
  "highlight_user": "Highlight one specific user's name.",
  "highlight_users": "Highlight all user names.",
  "highlight_colour": "Color for highlighted users in hex.",
  "selection_colour": "Color for selected users and files in hex.",
  "user_image_dir": "Folder containing avatar images named after users.",
  "default_user_image": "Fallback avatar image path.",
  "fixed_user_size": "Keep avatar sizes fixed instead of scaling dynamically.",
  "colour_images": "Colorize user avatar images.",
  "file_filter": "Hide files matching this filter pattern.",
  "file_show_filter": "Only show files matching this filter pattern.",
  "user_filter": "Hide users matching this filter pattern.",
  "user_show_filter": "Only show users matching this filter pattern.",
  "log_command": "Show the VCS log command Gource would use.",
  "log_format": "Specify the input log format, especially when reading from STDIN.",
  "git_branch": "Read a git branch other than the current one.",
  "output_ppm_stream": "Write a PPM frame stream to a file or - for stdout.",
  "output_framerate": "Framerate used with PPM stream output.",
  "output_custom_log": "Write the parsed history to Gource's custom log format.",
  "load_config": "Load a Gource config file before launching.",
  "save_config": "Save a Gource config file with the current options.",
}

GOURCE_OPTION_EXAMPLES: dict[str, str] = {
  "viewport": "1920x1080 or 1920x1080!",
  "screen": "1",
  "window_position": "100x80",
  "start_date": "2024-01-01",
  "stop_date": "2024-12-31",
  "start_position": "0.10",
  "stop_position": "0.90",
  "stop_at_time": "3600",
  "loop_delay_seconds": "3",
  "auto_skip_seconds": "1",
  "seconds_per_day": "24",
  "time_scale": "1.0",
  "file_idle_time": "0",
  "file_idle_time_at_end": "5",
  "padding": "1.1",
  "background": "111111",
  "max_files": "0",
  "max_file_lag": "-1",
  "max_user_speed": "500",
  "user_friction": "1",
  "hash_seed": "42",
  "title": "Interactive Commit History: My Project",
  "font_scale": "1.0",
  "font_size": "",
  "file_font_size": "16",
  "dir_font_size": "18",
  "user_font_size": "20",
  "font_colour": "FFFFFF",
  "date_format": "%Y-%m-%d",
  "logo_offset": "20x20",
  "caption_size": "28",
  "caption_colour": "FFFFFF",
  "caption_duration": "4",
  "caption_offset": "0",
  "filename_colour": "FFFFFF",
  "dir_colour": "88CCFF",
  "dir_name_depth": "3",
  "dir_name_position": "0.5",
  "filename_time": "2.0",
  "follow_user": "Jane Doe",
  "highlight_user": "Jane Doe",
  "highlight_colour": "FFD54F",
  "selection_colour": "00FFCC",
  "file_filter": "\\.png$",
  "file_show_filter": "\\.py$",
  "user_filter": "^bot",
  "user_show_filter": "alice|bob",
  "git_branch": "main",
}

GOURCE_OPTION_POPULATED_DEFAULTS: dict[str, str] = {
  "time_scale": "2",
  "file_idle_time_at_end": "600",
  "padding": "0",
  "max_files": "0",
  "max_user_speed": "500",
  "user_friction": "1",
  "user_scale": "0.1",
  "hash_seed": "42",
  "font_scale": "1.0",
  "file_font_size": "16",
  "dir_font_size": "14",
  "user_font_size": "20",
  "font_colour": "FFFFFF",
  "date_format": "%Y-%m-%d",
  "logo_offset": "20x20",
  "caption_size": "28",
  "caption_colour": "FFFFFF",
  "caption_duration": "4",
  "caption_offset": "0",
  "filename_colour": "FFFFFF",
  "dir_colour": "88CCFF",
  "dir_name_depth": "3",
  "dir_name_position": "0.5",
  "filename_time": "2.0",
}

GOURCE_OPTION_ENUMS: dict[str, list[str]] = {
  "camera_mode": ["overview", "track"],
  "crop": ["", "vertical", "horizontal"],
  "log_command": ["", "git", "svn", "hg", "bzr", "cvs2cl"],
  "log_format": ["", "git", "svn", "hg", "bzr", "cvs2cl", "custom"],
  "output_framerate": ["", "25", "30", "60"],
}

GOURCE_OPTION_RANGES: dict[str, tuple[float, float, int]] = {
  "bloom_multiplier": (0.0, 5.0, 100),
  "bloom_intensity": (0.0, 5.0, 100),
  "padding": (0.0, 2.0, 200),
  "user_scale": (0.1, 5.0, 98),
  "font_scale": (0.25, 4.0, 75),
}

GOURCE_OPTION_PATH_TYPES: dict[str, str] = {
  "background_image": "open_file",
  "font_file": "open_file",
  "caption_file": "open_file",
  "user_image_dir": "open_dir",
  "default_user_image": "open_file",
  "output_ppm_stream": "save_file",
  "output_custom_log": "save_file",
  "load_config": "open_file",
  "save_config": "save_file",
}

GOURCE_OPTION_COLOR_KEYS: set[str] = {
  "background",
  "font_colour",
  "caption_colour",
  "filename_colour",
  "dir_colour",
  "highlight_colour",
  "selection_colour",
}

GOURCE_OPTION_IMAGE_KEYS: set[str] = {
  "background_image",
  "default_user_image",
}

GOURCE_OPTION_SPECS: list[dict[str, Any]] = [
  {"key": "fullscreen", "label": "Fullscreen", "type": "bool", "tab": "Window", "flag": "-f", "default": False},
  {"key": "viewport", "label": "Viewport", "type": "string", "tab": "Window", "flag": "--viewport", "default": ""},
  {"key": "screen", "label": "Screen", "type": "string", "tab": "Window", "flag": "--screen", "default": ""},
  {"key": "high_dpi", "label": "High DPI", "type": "bool", "tab": "Window", "flag": "--high-dpi", "default": False},
  {"key": "window_position", "label": "Window Position", "type": "string", "tab": "Window", "flag": "--window-position", "default": ""},
  {"key": "frameless", "label": "Frameless", "type": "bool", "tab": "Window", "flag": "--frameless", "default": False},
  {"key": "transparent", "label": "Transparent Background", "type": "bool", "tab": "Window", "flag": "--transparent", "default": False},
  {"key": "disable_input", "label": "Disable Input", "type": "bool", "tab": "Window", "flag": "--disable-input", "default": False},

  {"key": "start_date", "label": "Start Date", "type": "string", "tab": "Timeline", "flag": "--start-date", "default": ""},
  {"key": "stop_date", "label": "Stop Date", "type": "string", "tab": "Timeline", "flag": "--stop-date", "default": ""},
  {"key": "start_position", "label": "Start Position", "type": "string", "tab": "Timeline", "flag": "--start-position", "default": ""},
  {"key": "stop_position", "label": "Stop Position", "type": "string", "tab": "Timeline", "flag": "--stop-position", "default": ""},
  {"key": "stop_at_time", "label": "Stop At Time", "type": "string", "tab": "Timeline", "flag": "--stop-at-time", "default": ""},
  {"key": "stop_at_end", "label": "Stop At End", "type": "bool", "tab": "Timeline", "flag": "--stop-at-end", "default": False},
  {"key": "loop", "label": "Loop", "type": "bool", "tab": "Timeline", "flag": "--loop", "default": False},
  {"key": "loop_delay_seconds", "label": "Loop Delay Seconds", "type": "string", "tab": "Timeline", "flag": "--loop-delay-seconds", "default": ""},
  {"key": "auto_skip_seconds", "label": "Auto Skip Seconds", "type": "string", "tab": "Timeline", "flag": "--auto-skip-seconds", "default": "1"},
  {"key": "seconds_per_day", "label": "Seconds Per Day", "type": "string", "tab": "Timeline", "flag": "--seconds-per-day", "default": "3"},
  {"key": "realtime", "label": "Realtime", "type": "bool", "tab": "Timeline", "flag": "--realtime", "default": False},
  {"key": "no_time_travel", "label": "No Time Travel", "type": "bool", "tab": "Timeline", "flag": "--no-time-travel", "default": False},
  {"key": "author_time", "label": "Author Time", "type": "bool", "tab": "Timeline", "flag": "--author-time", "default": False},
  {"key": "time_scale", "label": "Time Scale", "type": "string", "tab": "Timeline", "flag": "--time-scale", "default": ""},
  {"key": "file_idle_time", "label": "File Idle Time", "type": "string", "tab": "Timeline", "flag": "--file-idle-time", "default": "0"},
  {"key": "file_idle_time_at_end", "label": "File Idle Time At End", "type": "string", "tab": "Timeline", "flag": "--file-idle-time-at-end", "default": ""},

  {"key": "camera_mode", "label": "Camera Mode", "type": "string", "tab": "Scene", "flag": "--camera-mode", "default": "overview"},
  {"key": "crop", "label": "Crop Axis", "type": "string", "tab": "Scene", "flag": "--crop", "default": ""},
  {"key": "padding", "label": "Padding", "type": "string", "tab": "Scene", "flag": "--padding", "default": ""},
  {"key": "multi_sampling", "label": "Multi Sampling", "type": "bool", "tab": "Scene", "flag": "--multi-sampling", "default": False},
  {"key": "no_vsync", "label": "Disable VSync", "type": "bool", "tab": "Scene", "flag": "--no-vsync", "default": False},
  {"key": "background", "label": "Background Colour", "type": "string", "tab": "Scene", "flag": "--background-colour", "default": "111111"},
  {"key": "background_image", "label": "Background Image", "type": "string", "tab": "Scene", "flag": "--background-image", "default": ""},
  {"key": "bloom_multiplier", "label": "Bloom Mult (0 disables)", "type": "string", "tab": "Scene", "flag": "--bloom-multiplier", "default": "0"},
  {"key": "bloom_intensity", "label": "Bloom Intensity", "type": "string", "tab": "Scene", "flag": "--bloom-intensity", "default": "0"},
  {"key": "max_files", "label": "Max Files", "type": "string", "tab": "Scene", "flag": "--max-files", "default": ""},
  {"key": "max_file_lag", "label": "Max File Lag", "type": "string", "tab": "Scene", "flag": "--max-file-lag", "default": "1"},
  {"key": "max_user_speed", "label": "Max User Speed", "type": "string", "tab": "Scene", "flag": "--max-user-speed", "default": ""},
  {"key": "user_friction", "label": "User Friction", "type": "string", "tab": "Scene", "flag": "--user-friction", "default": ""},
  {"key": "user_scale", "label": "User Scale", "type": "string", "tab": "Scene", "flag": "--user-scale", "default": ""},
  {"key": "branch_elasticity", "label": "Elasticity", "type": "string", "tab": "Scene", "flag": "-e", "default": "0.0001"},
  {"key": "disable_auto_rotate", "label": "Disable Auto Rotate", "type": "bool", "tab": "Scene", "flag": "--disable-auto-rotate", "default": False},
  {"key": "hash_seed", "label": "Hash Seed", "type": "string", "tab": "Scene", "flag": "--hash-seed", "default": ""},

  {"key": "title", "label": "Title Override", "type": "string", "tab": "Labels", "flag": "--title", "default": ""},
  {"key": "font_file", "label": "Font File", "type": "string", "tab": "Labels", "flag": "--font-file", "default": ""},
  {"key": "font_scale", "label": "Font Scale", "type": "string", "tab": "Labels", "flag": "--font-scale", "default": ""},
  {"key": "font_size", "label": "Font Size", "type": "string", "tab": "Labels", "flag": "--font-size", "default": ""},
  {"key": "file_font_size", "label": "File Font Size", "type": "string", "tab": "Labels", "flag": "--file-font-size", "default": ""},
  {"key": "dir_font_size", "label": "Dir Font Size", "type": "string", "tab": "Labels", "flag": "--dir-font-size", "default": ""},
  {"key": "user_font_size", "label": "User Font Size", "type": "string", "tab": "Labels", "flag": "--user-font-size", "default": ""},
  {"key": "font_colour", "label": "Font Colour", "type": "string", "tab": "Labels", "flag": "--font-colour", "default": ""},
  {"key": "date_format", "label": "Date Format", "type": "string", "tab": "Labels", "flag": "--date-format", "default": ""},
  {"key": "logo_offset", "label": "Logo Offset", "type": "string", "tab": "Labels", "flag": "--logo-offset", "default": ""},
  {"key": "show_key", "label": "Show Extension Key", "type": "bool", "tab": "Labels", "flag": "--key", "default": True},
  {"key": "caption_file", "label": "Caption File", "type": "string", "tab": "Labels", "flag": "--caption-file", "default": ""},
  {"key": "caption_size", "label": "Caption Size", "type": "string", "tab": "Labels", "flag": "--caption-size", "default": ""},
  {"key": "caption_colour", "label": "Caption Colour", "type": "string", "tab": "Labels", "flag": "--caption-colour", "default": ""},
  {"key": "caption_duration", "label": "Caption Duration", "type": "string", "tab": "Labels", "flag": "--caption-duration", "default": ""},
  {"key": "caption_offset", "label": "Caption Offset", "type": "string", "tab": "Labels", "flag": "--caption-offset", "default": ""},
  {"key": "filename_colour", "label": "Filename Colour", "type": "string", "tab": "Labels", "flag": "--filename-colour", "default": ""},
  {"key": "dir_colour", "label": "Dir Colour", "type": "string", "tab": "Labels", "flag": "--dir-colour", "default": ""},
  {"key": "dir_name_depth", "label": "Dir Name Depth", "type": "string", "tab": "Labels", "flag": "--dir-name-depth", "default": ""},
  {"key": "dir_name_position", "label": "Dir Name Position", "type": "string", "tab": "Labels", "flag": "--dir-name-position", "default": ""},
  {"key": "filename_time", "label": "Filename Time", "type": "string", "tab": "Labels", "flag": "--filename-time", "default": ""},
  {"key": "file_extensions", "label": "File Extensions Only", "type": "bool", "tab": "Labels", "flag": "--file-extensions", "default": False},
  {"key": "file_extension_fallback", "label": "File Extension Fallback", "type": "bool", "tab": "Labels", "flag": "--file-extension-fallback", "default": False},

  {"key": "follow_user", "label": "Follow User", "type": "string", "tab": "Users", "flag": "--follow-user", "default": ""},
  {"key": "highlight_dirs", "label": "Highlight Dirs", "type": "bool", "tab": "Users", "flag": "--highlight-dirs", "default": False},
  {"key": "highlight_user", "label": "Highlight User", "type": "string", "tab": "Users", "flag": "--highlight-user", "default": ""},
  {"key": "highlight_users", "label": "Highlight Users", "type": "bool", "tab": "Users", "flag": "--highlight-users", "default": False},
  {"key": "highlight_colour", "label": "Highlight Colour", "type": "string", "tab": "Users", "flag": "--highlight-colour", "default": ""},
  {"key": "selection_colour", "label": "Selection Colour", "type": "string", "tab": "Users", "flag": "--selection-colour", "default": ""},
  {"key": "user_image_dir", "label": "User Image Dir", "type": "string", "tab": "Users", "flag": "--user-image-dir", "default": ""},
  {"key": "default_user_image", "label": "Default User Image", "type": "string", "tab": "Users", "flag": "--default-user-image", "default": ""},
  {"key": "fixed_user_size", "label": "Fixed User Size", "type": "bool", "tab": "Users", "flag": "--fixed-user-size", "default": False},
  {"key": "colour_images", "label": "Colour Images", "type": "bool", "tab": "Users", "flag": "--colour-images", "default": False},

  {"key": "file_filter", "label": "File Filter", "type": "string", "tab": "Filters", "flag": "--file-filter", "default": ""},
  {"key": "file_show_filter", "label": "File Show Filter", "type": "string", "tab": "Filters", "flag": "--file-show-filter", "default": ""},
  {"key": "user_filter", "label": "User Filter", "type": "string", "tab": "Filters", "flag": "--user-filter", "default": ""},
  {"key": "user_show_filter", "label": "User Show Filter", "type": "string", "tab": "Filters", "flag": "--user-show-filter", "default": ""},

  {"key": "log_command", "label": "Log Command", "type": "string", "tab": "Output", "flag": "--log-command", "default": ""},
  {"key": "log_format", "label": "Log Format", "type": "string", "tab": "Output", "flag": "--log-format", "default": ""},
  {"key": "git_branch", "label": "Git Branch", "type": "string", "tab": "Output", "flag": "--git-branch", "default": ""},
  {"key": "output_ppm_stream", "label": "Output PPM Stream", "type": "string", "tab": "Output", "flag": "-o", "default": ""},
  {"key": "output_framerate", "label": "Output Framerate", "type": "string", "tab": "Output", "flag": "-r", "default": ""},
  {"key": "output_custom_log", "label": "Output Custom Log", "type": "string", "tab": "Output", "flag": "--output-custom-log", "default": ""},
  {"key": "load_config", "label": "Load Gource Config", "type": "string", "tab": "Output", "flag": "--load-config", "default": ""},
  {"key": "save_config", "label": "Save Gource Config", "type": "string", "tab": "Output", "flag": "--save-config", "default": ""},
]

DEFAULT_GOURCE_HIDE_ELEMENTS: list[str] = [
  "bloom",
  "users",
  "usernames",
]

for _spec in GOURCE_OPTION_SPECS:
  _key = str(_spec["key"])
  if _spec.get("type") != "bool" and _spec.get("default", "") == "" and _key in GOURCE_OPTION_POPULATED_DEFAULTS:
    _spec["default"] = GOURCE_OPTION_POPULATED_DEFAULTS[_key]
  DEFAULT_CONFIG["gource_options"].setdefault(_spec["key"], _spec["default"])
DEFAULT_CONFIG["gource_options"].setdefault("hide", list(DEFAULT_GOURCE_HIDE_ELEMENTS))
DEFAULT_REPO_GOURCE_CONFIG["extra_args"] = list(DEFAULT_CONFIG["extra_args"])
DEFAULT_REPO_GOURCE_CONFIG["gource_options"] = json.loads(json.dumps(DEFAULT_CONFIG["gource_options"]))


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


def _prune_defaults(value: Any, default: Any) -> Any:
  if isinstance(value, dict) and isinstance(default, dict):
    out: dict[str, Any] = {}
    for key, sub_value in value.items():
      if key in default:
        pruned = _prune_defaults(sub_value, default[key])
        if pruned is not None:
          out[key] = pruned
      else:
        out[key] = sub_value
    return out or None
  if value == default:
    return None
  return value


def _extract_repo_gource_config(config: dict[str, Any] | None) -> dict[str, Any]:
  base = _deep_copy_json_dict(DEFAULT_REPO_GOURCE_CONFIG)
  if not isinstance(config, dict):
    return base
  overlay: dict[str, Any] = {}
  if "title_prefix" in config:
    overlay["title_prefix"] = config.get("title_prefix")
  if "logo_path" in config:
    overlay["logo_path"] = config.get("logo_path")
  if "extra_args" in config:
    overlay["extra_args"] = config.get("extra_args")
  if "gource_options" in config:
    overlay["gource_options"] = config.get("gource_options")
  merged = _deep_merge_dict(base, overlay)
  merged["logo_path"] = _path_to_forward_slashes(str(merged.get("logo_path", "")))
  gource_options = merged.get("gource_options", {})
  if isinstance(gource_options, dict):
    for spec in GOURCE_OPTION_SPECS:
      key = str(spec["key"])
      if key not in gource_options:
        continue
      if spec.get("type") == "bool":
        gource_options[key] = bool(gource_options.get(key, spec.get("default", False)))
        continue
      default_text = str(spec.get("default", ""))
      value_text = str(gource_options.get(key, "") or "").strip()
      if not value_text and default_text:
        gource_options[key] = default_text
    for key in GOURCE_OPTION_PATH_TYPES:
      if key in gource_options:
        gource_options[key] = _path_to_forward_slashes(str(gource_options.get(key, "")))
  return merged


def _extract_launcher_config(config: dict[str, Any] | None) -> dict[str, Any]:
  base = _deep_copy_json_dict(DEFAULT_LAUNCHER_CONFIG)
  if not isinstance(config, dict):
    return base
  overlay: dict[str, Any] = {}
  for key in DEFAULT_LAUNCHER_CONFIG:
    if key in config:
      overlay[key] = config.get(key)
  merged = _deep_merge_dict(base, overlay)
  merged["repo_path"] = _norm_dir(str(merged.get("repo_path", DEFAULT_LAUNCHER_CONFIG["repo_path"])))
  raw_recent = merged.get("recent_repo_paths", [])
  if isinstance(raw_recent, list):
    merged["recent_repo_paths"] = [ _norm_dir(str(p)) for p in raw_recent if str(p).strip() ]
  else:
    merged["recent_repo_paths"] = []
  return merged


def _repo_gource_config_path(repo_path: str) -> str:
  return os.path.join(repo_path, REPO_GOURCE_CONFIG_FILENAME)


def load_repo_gource_config(repo_path: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
  base = _extract_repo_gource_config(fallback)
  if not repo_path or not os.path.isdir(repo_path):
    return base
  repo_cfg = _read_json(_repo_gource_config_path(repo_path))
  if isinstance(repo_cfg, dict):
    return _deep_merge_dict(base, repo_cfg)
  return base


def _parse_float(value: Any) -> float | None:
  try:
    return float(str(value).strip())
  except (TypeError, ValueError):
    return None


def load_or_create_config() -> dict[str, Any]:
  template = _read_json(PATH_CONFIG_DEFAULT_JSON)
  template = _extract_launcher_config(template)
  user_cfg = _read_json(PATH_CONFIG_JSON)
  if isinstance(user_cfg, dict):
    normalized = _extract_launcher_config(_deep_merge_dict(template, user_cfg))
    if normalized != user_cfg:
      _write_json_atomic(PATH_CONFIG_JSON, normalized)
    return normalized
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


def _path_to_forward_slashes(path_value: str) -> str:
  return str(path_value).replace("\\", "/")


def _try_relpath(path_value: str, start: str) -> str:
  try:
    rel = os.path.relpath(path_value, start)
    return _path_to_forward_slashes(rel if rel else path_value)
  except Exception:
    return _path_to_forward_slashes(path_value)


def _load_preview_image(path_value: str, max_size: tuple[int, int] = (120, 72)):
  if not path_value or not os.path.isfile(path_value):
    return None
  try:
    if Image is not None:
      img = Image.open(path_value)
      img.thumbnail(max_size)
      return ctk.CTkImage(light_image=img.copy(), dark_image=img.copy(), size=img.size)
  except Exception:
    return None
  return None


def find_gource_executable(candidates: list[str]) -> str | None:
  for candidate in [*bundled_gource_candidates(), *candidates]:
    c = str(candidate or "").strip()
    if not c:
      continue
    if os.path.isabs(c) and _ensure_executable(c):
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
  extra_args = config.get("extra_args", [])
  if not isinstance(extra_args, list):
    extra_args = []

  title_prefix = str(config.get("title_prefix", "Interactive Commit History: ") or "")
  title_override = str(options.get("title", "") or "").strip()
  title = title_override or (f"{title_prefix}{project_name}" if project_name else title_prefix.rstrip())

  raw_hidden = options.get("hide", [])
  if isinstance(raw_hidden, str):
    hidden_elements = _split_csv_list(raw_hidden)
  elif isinstance(raw_hidden, list):
    hidden_elements = [str(x).strip() for x in raw_hidden if str(x).strip()]
  else:
    hidden_elements = []

  cmd: list[str] = [gource_executable]
  if sys.platform.startswith("linux") and gource_executable.lower().endswith(".appimage"):
    # Extraction mode avoids a host dependency on FUSE while still executing
    # the bundled native ELF payload.
    cmd.append("--appimage-extract-and-run")
  cmd.append("-f" if bool(options.get("fullscreen", True)) else "-w")
  if title:
    cmd.extend(["--title", title])

  skip_keys = {"fullscreen", "title", "bloom_multiplier", "bloom_intensity", "hide"}
  for spec in GOURCE_OPTION_SPECS:
    key = str(spec.get("key", ""))
    if key in skip_keys:
      continue
    flag = str(spec.get("flag", "") or "").strip()
    if not key or not flag:
      continue
    value = options.get(key, spec.get("default"))
    if spec.get("type") == "bool":
      if bool(value):
        cmd.append(flag)
      continue
    text = str(value or "").strip()
    if key == "padding":
      numeric = _parse_float(text)
      if numeric is None or numeric <= 0.0:
        continue
    if text:
      cmd.extend([flag, text])

  bloom_multiplier = _parse_float(options.get("bloom_multiplier", "0.5"))
  bloom_disabled = bloom_multiplier is not None and bloom_multiplier <= 0.0
  if bloom_disabled and "bloom" not in hidden_elements:
    hidden_elements.append("bloom")
  hidden_elements = _dedupe_keep_order(hidden_elements)
  if hidden_elements:
    cmd.extend(["--hide", ",".join(hidden_elements)])
  if bloom_disabled:
    pass
  else:
    cmd.extend(["--bloom-multiplier", str(options.get("bloom_multiplier", "0.5"))])
    cmd.extend(["--bloom-intensity", str(options.get("bloom_intensity", "0.5"))])

  logo_path_raw = str(config.get("logo_path", "") or "").strip()
  if logo_path_raw:
    logo_path = _resolve_path_from_repo(repo_path, logo_path_raw)
    if os.path.isfile(logo_path):
      cmd.extend(["--logo", logo_path])

  if extra_args:
    cmd.extend([str(x) for x in extra_args if str(x).strip()])

  return cmd


def _split_csv_list(value: str) -> list[str]:
  return [part.strip() for part in value.split(",") if part.strip()]


def _split_lines_list(value: str) -> list[str]:
  return [line.strip() for line in value.splitlines() if line.strip()]


def _norm_dir(path_value: str) -> str:
  return _path_to_forward_slashes(os.path.normpath(os.path.abspath(path_value)))


def _dedupe_keep_order(items: list[str]) -> list[str]:
  seen: set[str] = set()
  out: list[str] = []
  for item in items:
    if item in seen:
      continue
    seen.add(item)
    out.append(item)
  return out


def _filter_existing_dirs(items: list[str]) -> list[str]:
  out: list[str] = []
  for path_value in items:
    try:
      if os.path.isdir(path_value):
        out.append(path_value)
    except Exception:
      pass
  return out


# =============================================================================
# GUI App
# =============================================================================

class GitVisualHistoryApp(ctk.CTk):
  def __init__(self):
    super().__init__()

    self._legacy_repo_gource_fallback = _read_json(PATH_CONFIG_JSON)
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
    self._detached_gource_pids: set[int] = set()

    self._recent_repo_paths_max = int(self.config_data.get("recent_repo_paths_max", 16) or 16)
    if self._recent_repo_paths_max <= 0:
      self._recent_repo_paths_max = 16
    raw_recent = self.config_data.get("recent_repo_paths", [])
    if not isinstance(raw_recent, list):
      raw_recent = []
    self._recent_repo_paths: list[str] = []
    for p in raw_recent:
      if isinstance(p, str) and p.strip():
        try:
          self._recent_repo_paths.append(_norm_dir(p.strip()))
        except Exception:
          continue
    self._recent_repo_paths = _dedupe_keep_order(self._recent_repo_paths)
    self._recent_repo_paths = _filter_existing_dirs(self._recent_repo_paths)
    self._recent_repo_paths = self._recent_repo_paths[: self._recent_repo_paths_max]

    self.var_repo_path = tk.StringVar(value=_norm_dir(str(self.config_data.get("repo_path", DEFAULT_LAUNCHER_CONFIG["repo_path"]))))
    self.var_gource_execs = tk.StringVar(value=", ".join(self.config_data.get("gource_executables", ["gource", "gource.cmd"])))
    self.var_title_prefix = tk.StringVar(value=str(DEFAULT_REPO_GOURCE_CONFIG.get("title_prefix", "Interactive Commit History: ")))
    self.var_logo_path = tk.StringVar(value=str(DEFAULT_REPO_GOURCE_CONFIG.get("logo_path", "")))
    self.var_appearance_mode = tk.StringVar(value=str(self.config_data.get("appearance_mode", "System")))
    self.var_color_theme = tk.StringVar(value=str(self.config_data.get("color_theme", "blue")))
    self.var_prompt_before_launch = tk.BooleanVar(value=bool(self.config_data.get("prompt_before_launch", True)))
    self.var_prompt_before_close = tk.BooleanVar(value=bool(self.config_data.get("prompt_before_close", False)))
    g = self.config_data.get("gource_options", {})
    if not isinstance(g, dict):
      g = {}
    self.gource_vars: dict[str, tk.Variable] = {}
    for spec in GOURCE_OPTION_SPECS:
      key = str(spec["key"])
      raw_value = g.get(key, spec["default"])
      if spec["type"] == "bool":
        self.gource_vars[key] = tk.BooleanVar(value=bool(raw_value))
      else:
        self.gource_vars[key] = tk.StringVar(value=str(raw_value))

    raw_hidden = g.get("hide", [])
    if isinstance(raw_hidden, str):
      hidden_elements = set(_split_csv_list(raw_hidden))
    elif isinstance(raw_hidden, list):
      hidden_elements = {str(x).strip() for x in raw_hidden if str(x).strip()}
    else:
      hidden_elements = set()
    self.hide_vars: dict[str, tk.BooleanVar] = {
      key: tk.BooleanVar(value=(key in hidden_elements))
      for key, _label, _desc in GOURCE_HIDE_DISPLAY_ELEMENTS
    }

    self._build_ui()
    self._refresh_recent_repo_menu()

    self._apply_repo_gource_config_to_ui(
      load_repo_gource_config(
        self._resolve_repo_path_for_ui(),
        fallback=self._legacy_repo_gource_fallback,
      )
    )

    self.protocol("WM_DELETE_WINDOW", self._on_close)
    self.after(750, self._poll_process_state)
    self._log("App started.")

  def _build_ui(self) -> None:
    self.grid_columnconfigure(0, weight=1)
    self.grid_rowconfigure(1, weight=1)

    top = ctk.CTkFrame(self)
    top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
    top.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(top, text="Repo").grid(row=0, column=0, sticky="w", padx=(10, 6), pady=8)
    self.entry_repo = ctk.CTkComboBox(
      top,
      variable=self.var_repo_path,
      values=[],
      command=self._on_repo_combo_selected,
      state="normal",
    )
    self.entry_repo.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=8)
    ctk.CTkButton(top, text="Browse", width=90, command=self._choose_repo).grid(row=0, column=2, padx=(0, 6), pady=8)
    ctk.CTkButton(top, text="Clear History", width=120, command=self._on_clear_recent_repo_history).grid(row=0, column=3, padx=(0, 6), pady=8)
    ctk.CTkButton(top, text="Open Repo", width=100, command=self._open_repo_folder).grid(row=0, column=4, padx=(0, 10), pady=8)

    ctk.CTkLabel(top, text="Gource").grid(row=1, column=0, sticky="w", padx=(10, 6), pady=8)
    self.entry_execs = ctk.CTkEntry(top, textvariable=self.var_gource_execs)
    self.entry_execs.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=8)
    ctk.CTkButton(top, text="Detect", width=90, command=self._detect_gource).grid(row=1, column=2, padx=(0, 6), pady=8)
    ctk.CTkButton(top, text="Save Config", width=110, command=self._on_save).grid(row=1, column=3, padx=(0, 6), pady=8)
    ctk.CTkButton(top, text="Reset Defaults", width=120, command=self._on_reset_defaults).grid(row=1, column=4, padx=(0, 10), pady=8)

    middle = ctk.CTkTabview(self)
    middle.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)

    launcher_tab = middle.add("Launcher")
    launcher_tab.grid_rowconfigure(3, weight=1)
    launcher_tab.grid_columnconfigure(0, weight=1)
    launcher_tab.grid_columnconfigure(1, weight=1)
    launcher_tab.grid_columnconfigure(2, weight=1)

    self._labeled_option_menu(
      launcher_tab,
      0,
      0,
      "Appearance",
      self.var_appearance_mode,
      ["System", "Light", "Dark"],
      self._on_change_appearance_mode,
      "Choose the CustomTkinter appearance mode for the launcher window.",
      reset_command=lambda: self.var_appearance_mode.set(str(DEFAULT_LAUNCHER_CONFIG["appearance_mode"])),
      reset_var=self.var_appearance_mode,
      reset_default=str(DEFAULT_LAUNCHER_CONFIG["appearance_mode"]),
    )
    self._labeled_option_menu(
      launcher_tab,
      0,
      1,
      "Color Theme",
      self.var_color_theme,
      ["blue", "green", "dark-blue"],
      self._on_change_color_theme,
      "Choose the CustomTkinter color theme used by the launcher.",
      reset_command=lambda: self.var_color_theme.set(str(DEFAULT_LAUNCHER_CONFIG["color_theme"])),
      reset_var=self.var_color_theme,
      reset_default=str(DEFAULT_LAUNCHER_CONFIG["color_theme"]),
    )
    self._labeled_checkbox(launcher_tab, 1, 0, "Confirm before launch", self.var_prompt_before_launch, "Ask for confirmation before launching the visualization.", reset_command=lambda: self.var_prompt_before_launch.set(bool(DEFAULT_LAUNCHER_CONFIG["prompt_before_launch"])), reset_var=self.var_prompt_before_launch, reset_default=bool(DEFAULT_LAUNCHER_CONFIG["prompt_before_launch"]))
    self._labeled_checkbox(launcher_tab, 1, 1, "Notify after exit", self.var_prompt_before_close, "Show a dialog after the Gource process exits.", reset_command=lambda: self.var_prompt_before_close.set(bool(DEFAULT_LAUNCHER_CONFIG["prompt_before_close"])), reset_var=self.var_prompt_before_close, reset_default=bool(DEFAULT_LAUNCHER_CONFIG["prompt_before_close"]))

    actions = ctk.CTkFrame(launcher_tab)
    actions.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=(12, 8))
    actions.grid_columnconfigure(8, weight=1)

    self.btn_launch = ctk.CTkButton(actions, text="Launch Gource", command=self._on_launch)
    self.btn_launch.grid(row=0, column=0, padx=(0, 8), pady=8)
    self.btn_stop = ctk.CTkButton(actions, text="Terminate", command=self._on_terminate, fg_color="#aa3333", hover_color="#8d2a2a")
    self.btn_stop.grid(row=0, column=1, padx=(0, 8), pady=8)
    ctk.CTkButton(actions, text="Show Command", command=self._on_show_command).grid(row=0, column=2, padx=(0, 8), pady=8)

    self.lbl_status = ctk.CTkLabel(actions, text="Idle")
    self.lbl_status.grid(row=0, column=9, sticky="e", padx=(8, 0), pady=8)

    self.text_log = ctk.CTkTextbox(launcher_tab, font=ctk.CTkFont(family=MONOSPACE_FONT_FAMILY, size=12))
    self.text_log.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=10, pady=(0, 10))
    self.text_log.configure(state="disabled")

    options_tab = middle.add("Options")
    options_tab.grid_rowconfigure(0, weight=1)
    options_tab.grid_columnconfigure(0, weight=1)
    options_tabs = ctk.CTkTabview(options_tab)
    options_tabs.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

    controls_tab = middle.add("Controls")
    controls_tab.grid_rowconfigure(0, weight=1)
    controls_tab.grid_columnconfigure(0, weight=1)
    controls_box = ctk.CTkTextbox(controls_tab, font=ctk.CTkFont(family=MONOSPACE_FONT_FAMILY, size=12))
    controls_box.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    controls_box.insert("1.0", GOURCE_CONTROLS_TEXT)
    controls_box.configure(state="disabled")

    for tab_name in GOURCE_OPTION_TABS:
      tab = options_tabs.add(tab_name)
      tab.grid_rowconfigure(0, weight=1)
      tab.grid_columnconfigure(0, weight=1)
      scroll = ctk.CTkScrollableFrame(tab)
      scroll.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
      for col in range(3):
        scroll.grid_columnconfigure(col, weight=1)

      specs = [spec for spec in GOURCE_OPTION_SPECS if spec["tab"] == tab_name]
      row_offset = 0
      if tab_name == "Labels":
        specs = [spec for spec in specs if spec["key"] != "logo_offset"]
        branding = ctk.CTkFrame(scroll)
        branding.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
        for col in range(3):
          branding.grid_columnconfigure(col, weight=1)
        ctk.CTkLabel(branding, text="Branding").grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 4))
        self._labeled_entry(
          branding,
          1,
          0,
      "Title Prefix",
      self.var_title_prefix,
      "Prefix used when building the Gource window title for this repo.",
      reset_command=lambda: self.var_title_prefix.set(str(DEFAULT_REPO_GOURCE_CONFIG["title_prefix"])),
      reset_var=self.var_title_prefix,
      reset_default=str(DEFAULT_REPO_GOURCE_CONFIG["title_prefix"]),
    )
        self._labeled_image_path_entry(
          branding,
          1,
          1,
          "Logo Path",
          self.var_logo_path,
      "Logo image path. Gource has no separate logo-size option, so resize the source image if needed.",
      "open_file",
      browse_callback=self._browse_logo_path,
      reset_command=lambda: self.var_logo_path.set(str(DEFAULT_REPO_GOURCE_CONFIG["logo_path"])),
      reset_var=self.var_logo_path,
      reset_default=str(DEFAULT_REPO_GOURCE_CONFIG["logo_path"]),
    )
        self._add_gource_option_control(
          branding,
          1,
          2,
          next(spec for spec in GOURCE_OPTION_SPECS if spec["key"] == "logo_offset"),
        )
        row_offset = 2
      for index, spec in enumerate(specs):
        row = row_offset + (index // 3)
        col = index % 3
        self._add_gource_option_control(scroll, row, col, spec)

      if tab_name == "Scene":
        hide_row = (len(specs) + 2) // 3 + 1
        hide_frame = ctk.CTkFrame(scroll)
        hide_frame.grid(row=hide_row, column=0, columnspan=3, sticky="ew", padx=10, pady=(12, 8))
        for col in range(4):
          hide_frame.grid_columnconfigure(col, weight=1)
        ctk.CTkLabel(hide_frame, text="Hide Elements").grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(8, 4))
        for index, (key, label, desc) in enumerate(GOURCE_HIDE_DISPLAY_ELEMENTS):
          row = 1 + (index // 4)
          col = index % 4
          default_hidden = key in DEFAULT_GOURCE_HIDE_ELEMENTS
          self._labeled_checkbox(hide_frame, row, col, label, self.hide_vars[key], desc, reset_command=lambda v=self.hide_vars[key], d=default_hidden: v.set(d), reset_var=self.hide_vars[key], reset_default=default_hidden)

      if tab_name == "Output":
        extra_row = (len(specs) + 2) // 3 + 2
        ctk.CTkLabel(scroll, text="Extra Args (one per line)").grid(row=extra_row, column=0, columnspan=3, sticky="w", padx=10, pady=(8, 4))
        self.text_extra_args = ctk.CTkTextbox(scroll, height=100, font=ctk.CTkFont(family=MONOSPACE_FONT_FAMILY, size=12))
        self.text_extra_args.grid(row=extra_row + 1, column=0, columnspan=3, sticky="nsew", padx=10, pady=(0, 10))
        scroll.grid_rowconfigure(extra_row + 1, weight=1)

    self._refresh_running_state()

  def _labeled_entry(self, parent, row: int, col: int, label: str, var: tk.StringVar, desc: str = "", reset_command=None, reset_var=None, reset_default=None) -> None:
    frame = ctk.CTkFrame(parent)
    frame.grid(row=row, column=col, sticky="ew", padx=10, pady=6)
    frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(frame, text=label).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 2))
    ctk.CTkEntry(frame, textvariable=var).grid(row=1, column=0, sticky="ew", padx=(8, 4), pady=(0, 8))
    self._add_reset_button(frame, 1, 1, reset_command, reset_var=reset_var, reset_default=reset_default)
    self._add_field_description(frame, desc)

  def _labeled_path_entry(
    self,
    parent,
    row: int,
    col: int,
    label: str,
    var: tk.StringVar,
    desc: str,
    browse_mode: str,
    browse_callback=None,
    reset_command=None,
    reset_var=None,
    reset_default=None,
  ) -> None:
    frame = ctk.CTkFrame(parent)
    frame.grid(row=row, column=col, sticky="ew", padx=10, pady=6)
    frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(frame, text=label).grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(6, 2))
    ctk.CTkEntry(frame, textvariable=var).grid(row=1, column=0, sticky="ew", padx=(8, 4), pady=(0, 8))
    ctk.CTkButton(
      frame,
      text="Browse",
      width=80,
      command=browse_callback if browse_callback is not None else (lambda k=label, v=var, m=browse_mode: self._browse_gource_path(k, v, m)),
    ).grid(row=1, column=1, sticky="e", padx=(4, 4), pady=(0, 8))
    self._add_reset_button(frame, 1, 2, reset_command, reset_var=reset_var, reset_default=reset_default)
    self._add_field_description(frame, desc)

  def _labeled_image_path_entry(
    self,
    parent,
    row: int,
    col: int,
    label: str,
    var: tk.StringVar,
    desc: str,
    browse_mode: str,
    browse_callback=None,
    reset_command=None,
    reset_var=None,
    reset_default=None,
  ) -> None:
    frame = ctk.CTkFrame(parent)
    frame.grid(row=row, column=col, sticky="ew", padx=10, pady=6)
    frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(frame, text=label).grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(6, 2))
    ctk.CTkEntry(frame, textvariable=var).grid(row=1, column=0, sticky="ew", padx=(8, 4), pady=(0, 8))
    ctk.CTkButton(
      frame,
      text="Browse",
      width=80,
      command=browse_callback if browse_callback is not None else (lambda k=label, v=var, m=browse_mode: self._browse_gource_path(k, v, m)),
    ).grid(row=1, column=1, sticky="e", padx=(4, 4), pady=(0, 8))
    self._add_reset_button(frame, 1, 2, reset_command, reset_var=reset_var, reset_default=reset_default)

    preview = ctk.CTkLabel(frame, text="No preview", width=120, height=72)
    preview.grid(row=2, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 8))

    def update_preview(*_args) -> None:
      path_value = str(var.get() or "").strip()
      path_abs = self._resolve_repo_relative_path(path_value)
      image = _load_preview_image(path_abs)
      if image is not None:
        preview.configure(image=image, text="")
        preview._preview_image_ref = image  # type: ignore[attr-defined]
      else:
        preview.configure(image=None, text="No preview")
        preview._preview_image_ref = None  # type: ignore[attr-defined]

    var.trace_add("write", update_preview)
    update_preview()
    self._add_field_description(frame, desc, row=3)

  def _labeled_color_entry(
    self,
    parent,
    row: int,
    col: int,
    label: str,
    var: tk.StringVar,
    desc: str,
    reset_command=None,
    reset_var=None,
    reset_default=None,
  ) -> None:
    frame = ctk.CTkFrame(parent)
    frame.grid(row=row, column=col, sticky="ew", padx=10, pady=6)
    frame.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(frame, text=label).grid(row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(6, 2))

    preview = ctk.CTkLabel(frame, text="", width=28)
    preview.grid(row=1, column=0, sticky="w", padx=(8, 4), pady=(0, 8))
    ctk.CTkEntry(frame, textvariable=var).grid(row=1, column=1, sticky="ew", padx=(4, 4), pady=(0, 8))
    ctk.CTkButton(
      frame,
      text="Pick",
      width=64,
      command=lambda v=var, p=preview: self._pick_color(v, p),
    ).grid(row=1, column=2, sticky="e", padx=(4, 4), pady=(0, 8))
    self._add_reset_button(frame, 1, 3, reset_command, reset_var=reset_var, reset_default=reset_default)

    def update_preview(*_args) -> None:
      value = str(var.get() or "").strip().lstrip("#")
      if len(value) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in value):
        preview.configure(fg_color=f"#{value.upper()}")
      else:
        preview.configure(fg_color=("gray75", "gray25"))

    var.trace_add("write", update_preview)
    update_preview()
    self._add_field_description(frame, desc)

  def _labeled_slider_entry(
    self,
    parent,
    row: int,
    col: int,
    label: str,
    var: tk.StringVar,
    desc: str,
    min_value: float,
    max_value: float,
    steps: int,
    reset_command=None,
    reset_var=None,
    reset_default=None,
  ) -> None:
    frame = ctk.CTkFrame(parent)
    frame.grid(row=row, column=col, sticky="ew", padx=10, pady=6)
    frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(frame, text=label).grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(6, 2))
    entry = ctk.CTkEntry(frame, textvariable=var, width=90)
    entry.grid(row=1, column=1, sticky="e", padx=(4, 4), pady=(0, 8))
    slider = ctk.CTkSlider(frame, from_=min_value, to=max_value, number_of_steps=steps)
    slider.grid(row=1, column=0, sticky="ew", padx=(8, 4), pady=(0, 8))
    self._add_reset_button(frame, 1, 2, reset_command, reset_var=reset_var, reset_default=reset_default)

    sync_state = {"internal": False}

    def format_value(value: float) -> str:
      text = f"{value:.3f}".rstrip("0").rstrip(".")
      return text if text else "0"

    def on_slider(value: float) -> None:
      if sync_state["internal"]:
        return
      sync_state["internal"] = True
      try:
        var.set(format_value(float(value)))
      finally:
        sync_state["internal"] = False

    def on_var_change(*_args) -> None:
      if sync_state["internal"]:
        return
      try:
        numeric = float(str(var.get()).strip())
      except (TypeError, ValueError):
        return
      numeric = max(min_value, min(max_value, numeric))
      sync_state["internal"] = True
      try:
        slider.set(numeric)
      finally:
        sync_state["internal"] = False

    slider.configure(command=on_slider)
    var.trace_add("write", on_var_change)
    try:
      initial_numeric = float(str(var.get()).strip())
      initial_numeric = max(min_value, min(max_value, initial_numeric))
      slider.set(initial_numeric)
      if str(var.get()).strip():
        var.set(format_value(initial_numeric))
    except (TypeError, ValueError):
      slider.set(min_value)
      if str(var.get()).strip():
        var.set(format_value(min_value))

    self._add_field_description(frame, desc)

  def _labeled_option_menu(
    self,
    parent,
    row: int,
    col: int,
    label: str,
    var: tk.StringVar,
    values: list[str],
    command,
    desc: str = "",
    reset_command=None,
    reset_var=None,
    reset_default=None,
  ) -> None:
    frame = ctk.CTkFrame(parent)
    frame.grid(row=row, column=col, sticky="ew", padx=10, pady=6)
    frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(frame, text=label).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 2))
    kwargs: dict[str, Any] = {"variable": var, "values": values}
    if command is not None:
      kwargs["command"] = command
    ctk.CTkOptionMenu(frame, **kwargs).grid(row=1, column=0, sticky="ew", padx=(8, 4), pady=(0, 8))
    self._add_reset_button(frame, 1, 1, reset_command, reset_var=reset_var, reset_default=reset_default)
    self._add_field_description(frame, desc)

  def _labeled_checkbox(self, parent, row: int, col: int, label: str, var: tk.BooleanVar, desc: str = "", reset_command=None, reset_var=None, reset_default=None) -> None:
    frame = ctk.CTkFrame(parent)
    frame.grid(row=row, column=col, sticky="ew", padx=10, pady=6)
    frame.grid_columnconfigure(0, weight=1)
    ctk.CTkCheckBox(frame, text=label, variable=var).grid(row=0, column=0, sticky="w", padx=8, pady=8)
    self._add_reset_button(frame, 0, 1, reset_command, reset_var=reset_var, reset_default=reset_default)
    self._add_field_description(frame, desc)

  def _add_reset_button(self, parent, row: int, col: int, reset_command, reset_var=None, reset_default=None) -> None:
    if reset_command is None:
      return
    button = ctk.CTkButton(
      parent,
      text="Reset",
      width=58,
      command=reset_command,
      fg_color=("gray78", "gray28"),
      hover_color=("gray70", "gray22"),
      text_color=("gray10", "gray92"),
      text_color_disabled=("gray55", "gray45"),
    )
    button.grid(row=row, column=col, sticky="e", padx=(4, 8), pady=(0, 8) if row > 0 else 8)
    self._sync_reset_button_state(button, reset_var, reset_default)

  def _sync_reset_button_state(self, button, reset_var, reset_default) -> None:
    if reset_var is None:
      return
    theme_button = ctk.ThemeManager.theme["CTkButton"]
    enabled_fg = theme_button["fg_color"]
    enabled_hover = theme_button["hover_color"]
    enabled_text = theme_button["text_color"]
    disabled_text = theme_button["text_color_disabled"]

    def is_default() -> bool:
      current = reset_var.get()
      if isinstance(reset_var, tk.BooleanVar):
        return bool(current) == bool(reset_default)
      return str(current) == str(reset_default)

    def update(*_args) -> None:
      if is_default():
        button.configure(
          state="disabled",
          fg_color=("gray78", "gray28"),
          hover_color=("gray70", "gray22"),
          text_color=("gray10", "gray92"),
          text_color_disabled=("gray55", "gray45"),
        )
      else:
        button.configure(
          state="normal",
          fg_color=enabled_fg,
          hover_color=enabled_hover,
          text_color=enabled_text,
          text_color_disabled=disabled_text,
        )

    update()
    try:
      reset_var.trace_add("write", update)
    except Exception:
      pass

  def _add_field_description(self, parent, desc: str, row: int = 2) -> None:
    text = str(desc or "").strip()
    if not text:
      return
    try:
      column_count = max(int(parent.grid_size()[0]), 1)
    except Exception:
      column_count = 1
    ctk.CTkLabel(
      parent,
      text=text,
      justify="left",
      wraplength=640,
      font=ctk.CTkFont(size=11),
      text_color=("gray40", "gray70"),
    ).grid(row=row, column=0, columnspan=column_count, sticky="ew", padx=8, pady=(0, 8))

  def _add_gource_option_control(self, parent, row: int, col: int, spec: dict[str, Any]) -> None:
    key = str(spec["key"])
    var = self.gource_vars[key]
    desc = self._build_option_help_text(key, spec)
    default_value = spec.get("default")
    if spec["type"] == "bool":
      reset_command = lambda v=var, d=bool(default_value): v.set(d)
    else:
      reset_command = lambda v=var, d=str(default_value): v.set(d)
    if spec["type"] == "bool":
      self._labeled_checkbox(parent, row, col, str(spec["label"]), var, desc, reset_command=reset_command, reset_var=var, reset_default=bool(default_value))  # type: ignore[arg-type]
      return
    if key in GOURCE_OPTION_ENUMS:
      self._labeled_option_menu(parent, row, col, str(spec["label"]), var, GOURCE_OPTION_ENUMS[key], None, desc, reset_command=reset_command, reset_var=var, reset_default=str(default_value))  # type: ignore[arg-type]
      return
    if key in GOURCE_OPTION_COLOR_KEYS:
      self._labeled_color_entry(parent, row, col, str(spec["label"]), var, desc, reset_command=reset_command, reset_var=var, reset_default=str(default_value))  # type: ignore[arg-type]
      return
    if key in GOURCE_OPTION_IMAGE_KEYS:
      self._labeled_image_path_entry(parent, row, col, str(spec["label"]), var, desc, GOURCE_OPTION_PATH_TYPES.get(key, "open_file"), reset_command=reset_command, reset_var=var, reset_default=str(default_value))  # type: ignore[arg-type]
      return
    if key in GOURCE_OPTION_PATH_TYPES:
      self._labeled_path_entry(parent, row, col, str(spec["label"]), var, desc, GOURCE_OPTION_PATH_TYPES[key], reset_command=reset_command, reset_var=var, reset_default=str(default_value))  # type: ignore[arg-type]
      return
    if key in GOURCE_OPTION_RANGES:
      min_value, max_value, steps = GOURCE_OPTION_RANGES[key]
      self._labeled_slider_entry(parent, row, col, str(spec["label"]), var, desc, min_value, max_value, steps, reset_command=reset_command, reset_var=var, reset_default=str(default_value))  # type: ignore[arg-type]
      return
    self._labeled_entry(parent, row, col, str(spec["label"]), var, desc, reset_command=reset_command, reset_var=var, reset_default=str(default_value))  # type: ignore[arg-type]

  def _format_option_default_text(self, key: str, spec: dict[str, Any]) -> str:
    default_value = spec.get("default")
    if spec.get("type") == "bool":
      return "On" if bool(default_value) else "Off"
    default_text = str(default_value or "").strip()
    if default_text:
      return default_text
    if key in GOURCE_OPTION_PATH_TYPES:
      return "Unset"
    return "Unset (uses Gource default)"

  def _build_option_help_text(self, key: str, spec: dict[str, Any]) -> str:
    parts: list[str] = []
    desc = GOURCE_OPTION_DESCRIPTIONS.get(key, "").strip()
    if desc:
      parts.append(desc)
    parts.append(f"Default: {self._format_option_default_text(key, spec)}")
    if spec.get("type") != "bool" and key not in GOURCE_OPTION_ENUMS:
      if key in GOURCE_OPTION_RANGES:
        min_value, max_value, _steps = GOURCE_OPTION_RANGES[key]
        parts.append(f"Range: {min_value:g} to {max_value:g}.")
      example = GOURCE_OPTION_EXAMPLES.get(key, "").strip()
      if example:
        parts.append(f"Example: {example}")
    return "\n".join(parts)

  def _browse_gource_path(self, label: str, var: tk.StringVar, browse_mode: str) -> None:
    repo_base = self._resolve_repo_path_for_ui()
    initial_dir = repo_base if os.path.isdir(repo_base) else PATH_DIR_SCRIPT
    current = str(var.get() or "").strip()
    current_abs = _resolve_path_from_repo(repo_base, current) if repo_base else _resolve_path_from_script(current)
    if current_abs:
      if browse_mode == "open_dir" and os.path.isdir(current_abs):
        initial_dir = current_abs
      elif os.path.isfile(current_abs):
        initial_dir = os.path.dirname(current_abs)

    selected = ""
    if browse_mode == "open_dir":
      selected = filedialog.askdirectory(title=_dialog_title(label), initialdir=initial_dir) or ""
    elif browse_mode == "save_file":
      selected = filedialog.asksaveasfilename(title=_dialog_title(label), initialdir=initial_dir) or ""
    else:
      selected = filedialog.askopenfilename(title=_dialog_title(label), initialdir=initial_dir) or ""

    if not selected:
      return
    if repo_base and os.path.isdir(repo_base):
      var.set(_try_relpath(selected, repo_base))
    else:
      var.set(selected)

  def _resolve_repo_relative_path(self, path_value: str) -> str:
    repo_base = self._resolve_repo_path_for_ui()
    if repo_base and os.path.isdir(repo_base):
      return _resolve_path_from_repo(repo_base, path_value)
    return _resolve_path_from_script(path_value)

  def _pick_color(self, var: tk.StringVar, preview_widget) -> None:
    initial = str(var.get() or "").strip().lstrip("#")
    initial_color = f"#{initial}" if len(initial) == 6 else None
    _rgb, hex_value = colorchooser.askcolor(color=initial_color, title="Choose Color")
    if not hex_value:
      return
    var.set(str(hex_value).lstrip("#").upper())

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

  def _refresh_recent_repo_menu(self) -> None:
    values = list(self._recent_repo_paths)
    if not values:
      values = ["(none)"]
    self.entry_repo.configure(values=values, state="normal")

    cur = (self.var_repo_path.get() or "").strip()
    if (not cur) and values and values[0] != "(none)":
      self.var_repo_path.set(values[0])

  def _push_recent_repo(self, repo_path_abs: str) -> None:
    try:
      normalized = _norm_dir(repo_path_abs)
    except Exception:
      return
    if not os.path.isdir(normalized):
      return
    self._recent_repo_paths = [normalized] + [p for p in self._recent_repo_paths if p != normalized]
    self._recent_repo_paths = _dedupe_keep_order(self._recent_repo_paths)
    self._recent_repo_paths = _filter_existing_dirs(self._recent_repo_paths)
    self._recent_repo_paths = self._recent_repo_paths[: self._recent_repo_paths_max]
    self._refresh_recent_repo_menu()

  def _on_repo_combo_selected(self, value: str) -> None:
    if not value or value == "(none)":
      return
    self.var_repo_path.set(_norm_dir(value))
    self._load_repo_gource_config_into_ui(self._resolve_repo_path_for_ui())
    self._log(f"Repo selected: {value}")

  def _on_clear_recent_repo_history(self) -> None:
    if not messagebox.askyesno(APP_TITLE, "Clear recent project history?"):
      return
    self._recent_repo_paths = []
    self._refresh_recent_repo_menu()
    try:
      self._save_config()
    except Exception:
      pass
    self._log("Cleared recent project history.")

  def _choose_repo(self) -> None:
    initial = self._resolve_repo_path_for_ui()
    chosen = filedialog.askdirectory(
      title=_dialog_title("Select Repo"),
      initialdir=initial if os.path.isdir(initial) else PATH_DIR_SCRIPT,
    )
    if chosen:
      self.var_repo_path.set(_norm_dir(chosen))
      self._push_recent_repo(chosen)
      self._load_repo_gource_config_into_ui(chosen)
      self._log(f"Repo path set to: {self.var_repo_path.get()}")

  def _browse_logo_path(self) -> None:
    repo_path = self._resolve_repo_path_for_ui()
    initial_dir = repo_path if os.path.isdir(repo_path) else PATH_DIR_SCRIPT

    current = self.var_logo_path.get().strip()
    current_abs = _resolve_path_from_repo(repo_path, current) if repo_path else _resolve_path_from_script(current)
    if current_abs and os.path.isfile(current_abs):
      initial_dir = os.path.dirname(current_abs)

    chosen = filedialog.askopenfilename(title=_dialog_title("Select Logo"), initialdir=initial_dir)
    if not chosen:
      return

    if repo_path and os.path.isdir(repo_path):
      self.var_logo_path.set(_try_relpath(chosen, repo_path))
    else:
      self.var_logo_path.set(chosen)
    self._log(f"Logo path set to: {self.var_logo_path.get()}")

  def _detect_gource(self) -> None:
    candidates = _split_csv_list(self.var_gource_execs.get())
    found = find_gource_executable(candidates)
    if found:
      self._log(f"Gource found: {found}")
    else:
      self._log(f"Gource not found. Tried: {candidates or ['gource', 'gource.cmd']}")

  def _resolve_repo_path_for_ui(self) -> str:
    value = self.var_repo_path.get().strip()
    return _norm_dir(value) if value else ""

  def _apply_repo_gource_config_to_ui(self, repo_cfg: dict[str, Any]) -> None:
    self.var_title_prefix.set(str(repo_cfg.get("title_prefix", DEFAULT_REPO_GOURCE_CONFIG["title_prefix"])))
    self.var_logo_path.set(_path_to_forward_slashes(str(repo_cfg.get("logo_path", DEFAULT_REPO_GOURCE_CONFIG["logo_path"]))))

    self.text_extra_args.delete("1.0", "end")
    extra_args = repo_cfg.get("extra_args", [])
    if isinstance(extra_args, list):
      self.text_extra_args.insert("1.0", "\n".join(str(x) for x in extra_args if str(x).strip()))

    gource_options = repo_cfg.get("gource_options", {})
    if not isinstance(gource_options, dict):
      gource_options = {}
    merged_options = _deep_merge_dict(DEFAULT_REPO_GOURCE_CONFIG["gource_options"], gource_options)
    for spec in GOURCE_OPTION_SPECS:
      key = str(spec["key"])
      if key not in self.gource_vars:
        continue
      value = merged_options.get(key, spec.get("default"))
      if spec["type"] == "bool":
        self.gource_vars[key].set(bool(value))
      else:
        if key in GOURCE_OPTION_PATH_TYPES:
          self.gource_vars[key].set(_path_to_forward_slashes(str(value)))
        else:
          self.gource_vars[key].set(str(value))

    raw_hidden = merged_options.get("hide", [])
    if isinstance(raw_hidden, str):
      hidden_values = set(_split_csv_list(raw_hidden))
    elif isinstance(raw_hidden, list):
      hidden_values = {str(x).strip() for x in raw_hidden if str(x).strip()}
    else:
      hidden_values = set()
    for key, _label, _desc in GOURCE_HIDE_DISPLAY_ELEMENTS:
      self.hide_vars[key].set(key in hidden_values)

  def _load_repo_gource_config_into_ui(self, repo_path: str, *, fallback: dict[str, Any] | None = None) -> None:
    self._apply_repo_gource_config_to_ui(load_repo_gource_config(repo_path, fallback=fallback))

  def _apply_launcher_config_to_ui(self, launcher_cfg: dict[str, Any]) -> None:
    self.var_appearance_mode.set(str(launcher_cfg.get("appearance_mode", DEFAULT_LAUNCHER_CONFIG["appearance_mode"])))
    self.var_color_theme.set(str(launcher_cfg.get("color_theme", DEFAULT_LAUNCHER_CONFIG["color_theme"])))
    self.var_repo_path.set(_norm_dir(str(launcher_cfg.get("repo_path", DEFAULT_LAUNCHER_CONFIG["repo_path"]))))
    self.var_gource_execs.set(", ".join(launcher_cfg.get("gource_executables", DEFAULT_LAUNCHER_CONFIG["gource_executables"])))
    self.var_prompt_before_launch.set(bool(launcher_cfg.get("prompt_before_launch", DEFAULT_LAUNCHER_CONFIG["prompt_before_launch"])))
    self.var_prompt_before_close.set(bool(launcher_cfg.get("prompt_before_close", DEFAULT_LAUNCHER_CONFIG["prompt_before_close"])))

    self._recent_repo_paths_max = int(launcher_cfg.get("recent_repo_paths_max", DEFAULT_LAUNCHER_CONFIG["recent_repo_paths_max"]) or DEFAULT_LAUNCHER_CONFIG["recent_repo_paths_max"])
    if self._recent_repo_paths_max <= 0:
      self._recent_repo_paths_max = int(DEFAULT_LAUNCHER_CONFIG["recent_repo_paths_max"])
    raw_recent = launcher_cfg.get("recent_repo_paths", [])
    if not isinstance(raw_recent, list):
      raw_recent = []
    self._recent_repo_paths = []
    for p in raw_recent:
      if isinstance(p, str) and p.strip():
        try:
          self._recent_repo_paths.append(_norm_dir(p.strip()))
        except Exception:
          continue
    self._recent_repo_paths = _dedupe_keep_order(self._recent_repo_paths)
    self._recent_repo_paths = _filter_existing_dirs(self._recent_repo_paths)
    self._recent_repo_paths = self._recent_repo_paths[: self._recent_repo_paths_max]
    self._refresh_recent_repo_menu()

  def _collect_launcher_config_from_ui(self) -> dict[str, Any]:
    cfg = _deep_copy_json_dict(DEFAULT_LAUNCHER_CONFIG)
    cfg["window"]["width"] = max(self.winfo_width(), 900)
    cfg["window"]["height"] = max(self.winfo_height(), 680)
    cfg["appearance_mode"] = self.var_appearance_mode.get().strip() or "System"
    cfg["color_theme"] = self.var_color_theme.get().strip() or "blue"
    cfg["repo_path"] = self._resolve_repo_path_for_ui() or _norm_dir(str(DEFAULT_LAUNCHER_CONFIG["repo_path"]))
    cfg["recent_repo_paths_max"] = int(self._recent_repo_paths_max)
    cfg["recent_repo_paths"] = list(self._recent_repo_paths[: self._recent_repo_paths_max])
    cfg["gource_executables"] = _split_csv_list(self.var_gource_execs.get()) or ["gource", "gource.cmd"]
    cfg["prompt_before_launch"] = bool(self.var_prompt_before_launch.get())
    cfg["prompt_before_close"] = bool(self.var_prompt_before_close.get())
    return cfg

  def _collect_repo_gource_config_from_ui(self) -> dict[str, Any]:
    cfg = _deep_copy_json_dict(DEFAULT_REPO_GOURCE_CONFIG)
    cfg["title_prefix"] = self.var_title_prefix.get()
    cfg["logo_path"] = _path_to_forward_slashes(self.var_logo_path.get().strip())
    cfg["extra_args"] = _split_lines_list(self.text_extra_args.get("1.0", "end"))

    go = cfg["gource_options"]
    for spec in GOURCE_OPTION_SPECS:
      key = str(spec["key"])
      var = self.gource_vars[key]
      if spec["type"] == "bool":
        go[key] = bool(var.get())
      else:
        text = str(var.get()).strip()
        default = str(spec.get("default", ""))
        normalized_text = _path_to_forward_slashes(text) if key in GOURCE_OPTION_PATH_TYPES else text
        normalized_default = _path_to_forward_slashes(default) if key in GOURCE_OPTION_PATH_TYPES else default
        go[key] = normalized_text if normalized_text or not normalized_default else normalized_default
    go["fullscreen"] = bool(self.gource_vars["fullscreen"].get())
    go["hide"] = [key for key, _label, _desc in GOURCE_HIDE_DISPLAY_ELEMENTS if bool(self.hide_vars[key].get())]
    return cfg

  def _collect_config_from_ui(self) -> dict[str, Any]:
    cfg = self._collect_launcher_config_from_ui()
    cfg.update(self._collect_repo_gource_config_from_ui())
    return cfg

  def _save_repo_gource_config(self, repo_path: str) -> str:
    if not repo_path or not os.path.isdir(repo_path):
      raise ValueError(f"Repository path does not exist:\n{repo_path}")
    target = _repo_gource_config_path(repo_path)
    repo_cfg = self._collect_repo_gource_config_from_ui()
    repo_cfg_pruned = _prune_defaults(repo_cfg, DEFAULT_REPO_GOURCE_CONFIG)
    if isinstance(repo_cfg_pruned, dict) and repo_cfg_pruned:
      _write_json_atomic(target, repo_cfg_pruned)
    else:
      if os.path.isfile(target):
        os.remove(target)
    return target

  def _save_config(self) -> None:
    self.config_data = self._collect_launcher_config_from_ui()
    _write_json_atomic(PATH_CONFIG_JSON, self.config_data)

  def _on_save(self) -> None:
    try:
      self._save_config()
      repo_cfg_path = self._save_repo_gource_config(self._resolve_repo_path_for_ui())
      self._log(f"Saved launcher config: {PATH_CONFIG_JSON}")
      self._log(f"Saved repo Gource config: {repo_cfg_path}")
    except Exception as e:
      messagebox.showerror(APP_TITLE, f"Failed to save config:\n{e}")

  def _on_reset_defaults(self) -> None:
    if not messagebox.askyesno(APP_TITLE, "Reset all launcher and Gource options to defaults?"):
      return
    self._apply_launcher_config_to_ui(_deep_copy_json_dict(DEFAULT_LAUNCHER_CONFIG))
    self._apply_repo_gource_config_to_ui(_deep_copy_json_dict(DEFAULT_REPO_GOURCE_CONFIG))
    self._log("Reset all options to defaults in the UI.")

  def _build_launch_context(self) -> tuple[dict[str, Any], str, str, list[str]]:
    cfg = self._collect_config_from_ui()
    repo_path = _norm_dir(str(cfg.get("repo_path", DEFAULT_LAUNCHER_CONFIG["repo_path"])))
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
    self._push_recent_repo(repo_path)
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

    self._push_recent_repo(repo_path)

    if bool(cfg.get("prompt_before_launch", True)):
      ok = messagebox.askokcancel(
        APP_TITLE,
        f'Launch Gource for "{project_name}"?\n\nRepo:\n{repo_path}',
      )
      if not ok:
        self._log("Launch cancelled.")
        return

    try:
      self.config_data = self._collect_launcher_config_from_ui()
      _write_json_atomic(PATH_CONFIG_JSON, self.config_data)
      self._save_repo_gource_config(repo_path)
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
    proc_pid = int(proc.pid)
    try:
      rc = proc.wait()
    except Exception as e:
      if proc_pid in self._detached_gource_pids:
        self._detached_gource_pids.discard(proc_pid)
        return
      try:
        if self.winfo_exists():
          self.after(0, lambda: self._on_process_finished(-999, f"wait failed: {e}"))
      except Exception:
        pass
      return
    if proc_pid in self._detached_gource_pids:
      self._detached_gource_pids.discard(proc_pid)
      return
    try:
      if self.winfo_exists():
        self.after(0, lambda: self._on_process_finished(int(rc), None))
    except Exception:
      pass

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
    if not self.winfo_exists():
      return
    self._refresh_running_state()
    try:
      self.after(750, self._poll_process_state)
    except Exception:
      pass

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
      repo_path = self._resolve_repo_path_for_ui()
      if os.path.isdir(repo_path):
        self._save_repo_gource_config(repo_path)
    except Exception as e:
      self._log(f"Failed to save config on close: {e}")

    with self._proc_lock:
      proc = self._gource_process

    if proc and proc.poll() is None:
      if not messagebox.askyesno(APP_TITLE, "Gource is still running. Close launcher anyway?"):
        return
      pid = int(proc.pid)
      self._detached_gource_pids.add(pid)
      with self._proc_lock:
        if self._gource_process is proc:
          self._gource_process = None
      self._log(f"Gource is still running (pid={pid}). Detaching launcher and leaving Gource running.")
      self._refresh_running_state()

    self.destroy()


def main() -> int:
  set_windows_app_user_model_id(APP_USER_MODEL_ID)
  app = GitVisualHistoryApp()
  try:
    app.mainloop()
  except KeyboardInterrupt:
    try:
      app._log("Keyboard interrupt received. Closing launcher.")
    except Exception:
      pass
    try:
      if app.winfo_exists():
        app._on_close()
    except Exception:
      try:
        if app.winfo_exists():
          app.destroy()
      except Exception:
        pass
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
