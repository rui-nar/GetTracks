#!/usr/bin/env python
"""Build a release distribution of GetTracks.

Usage:
    python build_release.py [--version VERSION]

Produces:
    dist/GetTracks/          — single-folder build (run GetTracks.exe from there)
    dist/GetTracks-{ver}.zip — zipped archive ready for GitHub release upload
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def run(cmd: list, **kwargs):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"  ERROR: command exited with code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)


def get_version_from_git() -> str:
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, cwd=ROOT,
        )
        return result.stdout.strip().lstrip("v") or "0.0.0"
    except Exception:
        return "0.0.0"


def zip_dist(version: str) -> Path:
    folder = DIST / "GetTracks"
    zip_path = DIST / f"GetTracks-{version}-windows-x64.zip"
    print(f"\nZipping {folder} -> {zip_path}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in folder.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(DIST))
    print(f"  Created {zip_path.name} ({zip_path.stat().st_size // 1024:,} KB)")
    return zip_path


def main():
    parser = argparse.ArgumentParser(description="Build GetTracks release")
    parser.add_argument("--version", default=None, help="Version string (default: from git tag)")
    parser.add_argument("--clean", action="store_true", help="Delete build/ and dist/ first")
    args = parser.parse_args()

    version = args.version or get_version_from_git()
    print(f"\nBuilding GetTracks v{version}\n")

    if args.clean:
        for d in (BUILD, DIST):
            if d.exists():
                print(f"  Removing {d}")
                shutil.rmtree(d)

    # Run tests first (exclude test_oauth_real.py — requires live browser/network)
    print("Running tests…")
    run([sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short",
         "--ignore=tests/test_oauth_real.py"], cwd=ROOT)

    # PyInstaller build
    print("\nBuilding with PyInstaller…")
    run([sys.executable, "-m", "PyInstaller", "--clean", "GetTracks.spec"], cwd=ROOT)

    # Zip the output
    zip_path = zip_dist(version)

    print(f"\nBuild complete!")
    print(f"  Executable : dist/GetTracks/GetTracks.exe")
    print(f"  Archive    : {zip_path.relative_to(ROOT)}")
    print(f"\nTo create a GitHub release:")
    print(f"  gh release create v{version} {zip_path} --title 'GetTracks v{version}' --generate-notes")


if __name__ == "__main__":
    main()
