# Validation

Static evidence confirms separate Mach-O arm64 and x86-64 executables, no
unrelocated Homebrew dynamic-library paths, and no missing non-system dylibs.
The cache wrapper removes quarantine metadata and ad-hoc signs the copied
binaries before launch. Runtime and Gatekeeper evidence are not available yet.
Do not promote this plan until a native macOS executor is available.
