# Packaging

## Building the desktop bundle

```bash
uv run python scripts/build_desktop.py
uv run python scripts/build_desktop.py --skip-frontend   # reuse the existing UI build
```

This builds the frontend, then bundles Python, Qt and the UI into
`dist/sarmesh/`. The result runs on a machine with no Python, no uv and no Node
installed. `dist/sarmesh/sarmesh` is the executable.

Expect roughly 580 MB. Most of it is `libQt6WebEngineCore` at around 194 MB,
which is Chromium. That is the same reason an Electron app is large, and it is
the cost of depending on no system browser. The spec prunes what a
single-purpose offline app never reads: non-English locales, Qt translations,
devtools resources and QML.

The bundle is built **onedir** rather than onefile, because QtWebEngine spawns a
helper process that has to find Qt's resources on disk. Onefile's
extract-to-temp behaviour makes that both fragile and slow to start, and the
directory is what gets wrapped in an installer or AppImage anyway.

## Building a wheel

```bash
npm --prefix frontend run build
uv build --wheel
```

The compiled UI must exist first. It is gitignored, and hatchling excludes
VCS-ignored files by default, so `pyproject.toml` lists it under `artifacts`.
Without that the wheel installs with no UI to serve.

## Building for other platforms

PyInstaller bundles the host's real interpreter and native libraries, so it
cannot cross-compile. That does not mean you need three machines.

**CI is the intended route.**
[`.github/workflows/build.yml`](../.github/workflows/build.yml) runs one native
job per target and uploads each as an artifact. Push a tag and collect the
builds. Native arm64 runners are free for public repositories; private repos
need a paid plan.

**Windows** must be built on Windows, either through the CI job or a VM.

**Raspberry Pi** needs **Pi OS Trixie or newer**. PySide6's arm64 wheels require
glibc 2.39 and Bookworm ships 2.36. [`packaging/Dockerfile.arm64`](../packaging/Dockerfile.arm64)
is based on Debian Trixie for that reason, and can build the arm64 bundle on an
x86_64 machine under QEMU emulation. It is slow, tens of minutes, but needs no
Pi. There is no driver script for it yet; run the container by hand.

## What ships where

Node is a build-time dependency only. Nothing Node-related reaches a Pi or an
end user's machine, which receive the compiled static files.

The packaged app is built windowed and has no console. On Windows there is no
stdout at all, and a double-clicked macOS `.app` has none worth reading.
Anything fatal is written to the log and shown in a dialog naming its location.
See [operations.md](operations.md#logs).
