# Workspace constraints

- Work only inside `C:/SahilAppProjects/KinokoDS`. Reading internet resources and
  downloading files into this folder are allowed. Do not write temporary files,
  caches, downloads, or build artifacts elsewhere.
- Keep the entire folder strictly below 200,000,000 bytes, including `.git`,
  ignored files, and builds. Use `tools/check-size.ps1` before/after builds and
  downloads. Estimate output sizes before operations; the check is an audit,
  not a filesystem quota. Leave substantial headroom (target below 160 MB).
- No automatic dependency/toolchain downloads. Use installed tools; keep build
  outputs in `build/`. Point TEMP/TMP at `build/tmp` during builds and tests.
- Do not represent synthetic fixtures or unverified equations as MKDS physics.
