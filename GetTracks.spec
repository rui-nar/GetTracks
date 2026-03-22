# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for GetTracks — produces a single-folder Windows build."""

import sys
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=[],
    datas=[
        # App assets
        (str(ROOT / "assets"), "assets"),
        # Config template — user must fill in credentials
        (str(ROOT / "config" / "config.json"), "config"),
        # ffmpeg binary bundled via imageio-ffmpeg
        (str(ROOT / ".venv" / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries"), "imageio_ffmpeg/binaries"),
    ],
    hiddenimports=[
        # All src sub-packages (PyInstaller needs explicit help with src.* layout)
        "src",
        "src.api",
        "src.auth",
        "src.cache",
        "src.config",
        "src.exceptions",
        "src.filters",
        "src.gpx",
        "src.gui",
        "src.models",
        "src.polarsteps_api",
        "src.polarsteps_api.models",
        "src.project",
        "src.animation",
        "src.utils",
        "src.visualization",
        # Pydantic (Polarsteps API models)
        "pydantic",
        "pydantic.v1",
        "pydantic_settings",
        "cachetools",
        # PyQt6 networking (tile fetching)
        "PyQt6.QtNetwork",
        # Strava / OAuth
        "requests",
        "requests.adapters",
        "requests.packages",
        # GPX
        "gpxpy",
        "lxml",
        # Polyline codec
        "polyline",
        # Animation / video export
        "imageio",
        "imageio_ffmpeg",
        "numpy",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "pandas",
        "scipy",
        "IPython",
        "tkinter",
        "wx",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GetTracks",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "app_icon.png"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="GetTracks",
)
