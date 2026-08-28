#!/usr/bin/env python3
"""Build the distributable SARMesh desktop app.

Written in Python rather than shell so the same command works on the Linux,
Raspberry Pi and Windows machines this gets built for.

    uv run python scripts/build_desktop.py
    uv run python scripts/build_desktop.py --skip-frontend
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
SPEC = ROOT / "packaging" / "sarmesh.spec"
DIST = ROOT / "dist" / "sarmesh"


def run(command: list[str], cwd: Path) -> None:
    print(f"\n$ {' '.join(command)}")
    result = subprocess.run(command, cwd=cwd, check=False)

    if result.returncode != 0:
        raise SystemExit(f"failed: {' '.join(command)}")


def build_frontend() -> None:
    npm = shutil.which("npm")

    if npm is None:
        raise SystemExit(
            "npm not found. Node is needed to build the UI, but only on this "
            "build machine -- it is not required to run the packaged app."
        )

    if not (FRONTEND / "node_modules").is_dir():
        run([npm, "install"], cwd=FRONTEND)

    run([npm, "run", "build"], cwd=FRONTEND)


def directory_size(path: Path) -> float:
    # Qt ships chains of symlinks next to each library; following them would
    # count the same bytes several times over and badly overstate the bundle.
    return (
        sum(
            f.stat().st_size
            for f in path.rglob("*")
            if f.is_file() and not f.is_symlink()
        )
        / 1e6
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="Reuse the existing frontend build",
    )
    args = parser.parse_args()

    if args.skip_frontend:
        print("Skipping frontend build")
    else:
        build_frontend()

    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(ROOT / "dist"),
            "--workpath",
            str(ROOT / "build"),
            str(SPEC),
        ],
        cwd=ROOT,
    )

    if not DIST.is_dir():
        raise SystemExit(f"expected bundle at {DIST}")

    print(f"\nBuilt {DIST}  ({directory_size(DIST):.0f} MB)")
    print(f"Run it with: {DIST / 'sarmesh'}")


if __name__ == "__main__":
    main()
