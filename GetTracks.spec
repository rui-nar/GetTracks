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
        "src.utils",
        "src.visualization",
        # PyQt6 WebEngine requires explicit inclusion
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebChannel",
        # Folium writes Jinja2 templates at runtime
        "folium",
        "jinja2",
        "branca",
        # Strava / OAuth
        "requests",
        "requests.adapters",
        "requests.packages",
        # GPX
        "gpxpy",
        "lxml",
        # Polyline codec
        "polyline",
        # Keyring backends (include common ones for portability)
        "keyring.backends.Windows",
        "keyring.backends.fail",
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
