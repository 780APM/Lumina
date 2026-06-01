"""Run Lumina as a module."""

from __future__ import annotations

try:
    from .ui.main_window import run
except ImportError:
    from ui.main_window import run


if __name__ == "__main__":
    run()
