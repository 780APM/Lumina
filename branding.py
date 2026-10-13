"""Locate packaged artwork and apply Lumina's Windows application identity."""

from pathlib import Path
import sys


def asset_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "assets" / name


def set_windows_app_id() -> None:
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Lumina.Player")
