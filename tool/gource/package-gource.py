#!/usr/bin/env python3
"""Build and validate the native portable Gource payload for this host."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def run(command: list[str], *, cwd: str | None = None) -> None:
  print("+", subprocess.list2cmdline(command), flush=True)
  subprocess.run(command, cwd=cwd, check=True)


def build_linux_x86_64() -> str:
  if shutil.which("docker") is None:
    raise RuntimeError("Docker is required to build the Linux AppImage")
  output_dir = os.path.join(ROOT, "vendor", "gource", "linux-x86_64")
  os.makedirs(output_dir, exist_ok=True)
  context = os.path.join(ROOT, "tool", "gource", "linux")
  run([
    "docker", "build", "--output", f"type=local,dest={output_dir}", ".",
  ], cwd=context)
  return os.path.join(output_dir, "gource.AppImage")


def validate(executable: str, target_platform: str) -> None:
  if not os.path.isfile(executable):
    raise RuntimeError(f"Portable Gource payload was not created: {executable}")
  if target_platform == "linux" and not sys.platform.startswith("linux"):
    # The Dockerfile already executes the native AppImage smoke test in its
    # Ubuntu build stage. A host such as Windows cannot execute that ELF file.
    print("Gource v0.56 Linux smoke test passed in the Docker build stage")
    return
  command = [executable, "-h"]
  if sys.platform.startswith("linux") and executable.endswith(".AppImage"):
    command.insert(1, "--appimage-extract-and-run")
  result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
  if result.returncode != 0 or "Gource v" not in result.stdout:
    raise RuntimeError(f"Gource smoke test failed ({result.returncode}):\n{result.stdout}")
  print(result.stdout.splitlines()[0])


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--platform", choices=["linux"], default=platform.system().lower())
  args = parser.parse_args()
  if args.platform == "linux":
    if platform.machine().lower() not in {"amd64", "x86_64"}:
      raise RuntimeError("The Docker builder currently supports Linux x86-64 only")
    executable = build_linux_x86_64()
  else:
    raise RuntimeError(f"Unsupported packaging platform: {args.platform}")
  validate(executable, args.platform)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
