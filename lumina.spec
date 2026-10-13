# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files
from pathlib import Path


datas = collect_data_files("customtkinter")
asset_root = Path(SPECPATH) / "assets"
datas += [(str(asset_root / name), "assets") for name in ("lumina.png", "lumina.ico")]
hiddenimports = [
    # miniaudio's CFFI extensions are loaded by its compiled module and are not
    # reliably discovered from a one-file build's import graph.
    "_cffi_backend",
    "_miniaudio",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.backends._backend_tk",
    "PIL.Image",
    "PIL.ImageTk",
    "mutagen.mp3",
    "mutagen.flac",
    "mutagen.oggvorbis",
    "mutagen.wave",
    "miniaudio",
    "numpy",
]


a = Analysis(
    ["__main__.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Lumina",
    icon=str(asset_root / "lumina.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # Avoid requiring UPX and reduce antivirus false positives for releases.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
