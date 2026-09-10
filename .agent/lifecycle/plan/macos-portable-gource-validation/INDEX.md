# macOS Portable Gource Validation

Wishlist plan for validating the native macOS Gource payloads independently
from the normal Windows and Linux release milestones.

Native arm64 and x86-64 payloads are packaged with closed bundle-relative
dependency graphs. The remaining acceptance boundary is successful launcher
discovery and a native Gource smoke test on both Apple silicon (`arm64`) and
Intel (`x86_64`) macOS. This host cannot supply that runtime evidence, so the
plan remains separate and unpromoted.
