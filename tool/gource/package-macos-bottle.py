#!/usr/bin/env python3
"""Create relocatable native macOS Gource bundles from Homebrew bottles.

Requires the `lief` package. This builder may run on Windows, Linux, or macOS;
runtime signing and validation intentionally happen on the destination Mac.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import tarfile
import urllib.parse
import urllib.request

import lief


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API = "https://formulae.brew.sh/api/formula/{name}.json"
SYSTEM_PREFIXES = ("/System/Library/", "/usr/lib/")


def read_json(url: str) -> dict:
  with urllib.request.urlopen(url) as response:
    return json.load(response)


def download_bottle(url: str, sha256: str, destination: str) -> None:
  if os.path.isfile(destination):
    with open(destination, "rb") as source:
      if hashlib.file_digest(source, "sha256").hexdigest() == sha256:
        return
  match = re.search(r"ghcr\.io/v2/(.+?)/blobs/", url)
  headers: dict[str, str] = {}
  if match:
    repository = match.group(1)
    token_url = "https://ghcr.io/token?" + urllib.parse.urlencode({
      "service": "ghcr.io",
      "scope": f"repository:{repository}:pull",
    })
    headers["Authorization"] = f"Bearer {read_json(token_url)['token']}"
  request = urllib.request.Request(url, headers=headers)
  with urllib.request.urlopen(request) as response, open(destination, "wb") as target:
    shutil.copyfileobj(response, target)
  with open(destination, "rb") as source:
    actual = hashlib.file_digest(source, "sha256").hexdigest()
  if actual != sha256:
    raise RuntimeError(f"Bottle checksum mismatch: expected {sha256}, got {actual}")


def historical_bottle(name: str, bottle_key: str, files: dict, source_path: str) -> dict | None:
  path = source_path
  commits_url = "https://api.github.com/repos/Homebrew/homebrew-core/commits?" + urllib.parse.urlencode({
    "path": path,
    "per_page": 50,
  })
  pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(bottle_key)}:\s*\"([0-9a-f]{{64}})\"")
  for commit in read_json(commits_url):
    raw_url = f"https://raw.githubusercontent.com/Homebrew/homebrew-core/{commit['sha']}/{path}"
    with urllib.request.urlopen(raw_url) as response:
      source = response.read().decode("utf-8")
    match = pattern.search(source)
    if match:
      repository_url = next(iter(files.values()))["url"].rsplit("/blobs/", 1)[0]
      return {
        "url": f"{repository_url}/blobs/sha256:{match.group(1)}",
        "sha256": match.group(1),
      }
  return None


def acquire_formula(name: str, bottle_key: str, cache: str, seen: set[str], *, required: bool = False) -> None:
  if name in seen:
    return
  seen.add(name)
  metadata = read_json(API.format(name=urllib.parse.quote(name, safe="@")))
  files = metadata["bottle"]["stable"]["files"]
  bottle = files.get(bottle_key) or historical_bottle(name, bottle_key, files, metadata["ruby_source_path"])
  if bottle is None:
    if required:
      raise RuntimeError(f"No {bottle_key} bottle is available for {name}")
    print(f"Skipping {name}: no {bottle_key} bottle is currently published")
    seen.remove(name)
    return
  formula_cache = os.path.join(cache, name.replace("@", "_"))
  os.makedirs(formula_cache, exist_ok=True)
  archive = os.path.join(formula_cache, "bottle.tar.gz")
  marker = os.path.join(formula_cache, ".extracted")
  download_bottle(bottle["url"], bottle["sha256"], archive)
  if not os.path.isfile(marker):
    with tarfile.open(archive, "r:gz") as bundle:
      bundle.extractall(formula_cache, filter="data")
    open(marker, "w", encoding="utf-8").close()
  for dependency in metadata.get("dependencies", []):
    acquire_formula(dependency, bottle_key, cache, seen)


def find_formula_root(cache: str, name: str) -> str:
  base = os.path.join(cache, name.replace("@", "_"), name)
  versions = [entry.path for entry in os.scandir(base) if entry.is_dir()]
  if len(versions) != 1:
    raise RuntimeError(f"Expected one extracted version for {name}, found {versions}")
  return versions[0]


def index_libraries(cache: str, formulae: set[str]) -> dict[str, str]:
  result: dict[str, str] = {}
  for formula in formulae:
    root = find_formula_root(cache, formula)
    for directory, _subdirs, files in os.walk(root):
      for filename in files:
        if ".dylib" in filename:
          result.setdefault(filename, os.path.join(directory, filename))
  return result


def parse_macho(path: str):
  container = lief.MachO.parse(path)
  if container is None or len(container) != 1:
    raise RuntimeError(f"Unable to parse Mach-O file: {path}")
  return container, container.at(0)


def linked_libraries(path: str) -> list[str]:
  _container, binary = parse_macho(path)
  return [command.name for command in binary.libraries]


def patch_macho(path: str) -> None:
  dependencies = linked_libraries(path)
  with open(path, "rb") as source:
    content = source.read()
  for dependency in dependencies:
    if dependency.startswith(SYSTEM_PREFIXES) or dependency.startswith(("@rpath/", "@loader_path/")):
      continue
    old = dependency.encode("utf-8")
    new = ("@loader_path/" + os.path.basename(dependency)).encode("utf-8")
    if len(new) > len(old):
      raise RuntimeError(f"Relocated Mach-O path is too long: {dependency}")
    replacement = new + (b"\0" * (len(old) - len(new)))
    if old not in content:
      raise RuntimeError(f"Mach-O dependency path was not found in {path}: {dependency}")
    content = content.replace(old, replacement)
  with open(path, "wb") as target:
    target.write(content)


def package(architecture: str, work_dir: str) -> str:
  bottle_key = "arm64_sonoma" if architecture == "arm64" else "sonoma"
  cache = os.path.join(work_dir, bottle_key)
  os.makedirs(cache, exist_ok=True)
  formulae: set[str] = set()
  acquire_formula("gource", bottle_key, cache, formulae, required=True)
  library_index = index_libraries(cache, formulae)
  gource_root = find_formula_root(cache, "gource")
  source_binary = os.path.join(gource_root, "bin", "gource")
  output = os.path.join(ROOT, "vendor", "gource", f"macos-{architecture}")
  os.makedirs(output, exist_ok=True)
  binary_output = os.path.join(output, "gource-bin")
  if os.path.exists(binary_output):
    os.chmod(binary_output, os.stat(binary_output).st_mode | stat.S_IWUSR)
  shutil.copy2(source_binary, binary_output)
  shutil.copytree(os.path.join(gource_root, "share", "gource"), os.path.join(output, "data"), dirs_exist_ok=True)
  for filename in ("COPYING", "README.md", "ChangeLog"):
    shutil.copy2(os.path.join(gource_root, filename), os.path.join(output, filename))
  license_root = os.path.join(output, "license")
  for formula in formulae:
    formula_root = find_formula_root(cache, formula)
    formula_license_root = os.path.join(license_root, formula.replace("@", "_"))
    for entry in os.scandir(formula_root):
      if entry.is_file() and entry.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
        os.makedirs(formula_license_root, exist_ok=True)
        shutil.copy2(entry.path, os.path.join(formula_license_root, entry.name))

  pending = [binary_output]
  copied: set[str] = set()
  while pending:
    current = pending.pop()
    for dependency in linked_libraries(current):
      if dependency.startswith(SYSTEM_PREFIXES):
        continue
      basename = os.path.basename(dependency)
      if basename in copied:
        continue
      source = library_index.get(basename)
      if source is None:
        raise RuntimeError(f"Unable to resolve {dependency} required by {current}")
      destination = os.path.join(output, basename)
      if os.path.exists(destination):
        os.chmod(destination, os.stat(destination).st_mode | stat.S_IWUSR)
      shutil.copy2(source, destination, follow_symlinks=True)
      copied.add(basename)
      pending.append(destination)

  for filename in os.listdir(output):
    path = os.path.join(output, filename)
    if os.path.isfile(path):
      os.chmod(path, os.stat(path).st_mode | stat.S_IWUSR | stat.S_IXUSR)
  patch_macho(binary_output)
  for basename in copied:
    patch_macho(os.path.join(output, basename))
  return output


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("architecture", choices=["arm64", "x86_64"])
  parser.add_argument("--work-dir", required=True)
  args = parser.parse_args()
  print(package(args.architecture, os.path.abspath(args.work_dir)))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
