"""Validated per-user settings storage for Lumina."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

DEFAULT_SETTINGS = {
    "accent": "#1db954",
    "viz_3d": False,
    "viz_circular": False,
}
LEGACY_SETTINGS_FILE = Path(__file__).with_name("settings.json")
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def settings_file() -> Path:
    """Return the platform-appropriate per-user settings path."""
    if os.name == "nt" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "Lumina" / "settings.json"
    if os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]) / "lumina" / "settings.json"
    return Path.home() / ".config" / "lumina" / "settings.json"


def load_settings(
    path: Path | None = None,
    legacy_path: Path | None = LEGACY_SETTINGS_FILE,
) -> dict[str, Any]:
    """Load and validate settings, optionally falling back to a legacy file."""
    primary = path or settings_file()
    candidates = [primary]
    if legacy_path is not None and legacy_path != primary:
        candidates.append(legacy_path)

    for candidate in candidates:
        try:
            raw = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(raw, dict):
            return _validated(raw)
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: Mapping[str, Any], path: Path | None = None) -> bool:
    """Atomically save validated settings. Returns whether the write succeeded."""
    destination = path or settings_file()
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(_validated(settings), indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
        return True
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _validated(settings: Mapping[str, Any]) -> dict[str, Any]:
    accent = settings.get("accent")
    viz_3d = settings.get("viz_3d")
    viz_circular = settings.get("viz_circular")
    valid_viz_3d = viz_3d if isinstance(viz_3d, bool) else DEFAULT_SETTINGS["viz_3d"]
    valid_viz_circular = (
        viz_circular
        if isinstance(viz_circular, bool)
        else DEFAULT_SETTINGS["viz_circular"]
    )
    if valid_viz_3d and valid_viz_circular:
        valid_viz_circular = False
    return {
        "accent": (
            accent
            if isinstance(accent, str) and _HEX_COLOR.fullmatch(accent)
            else DEFAULT_SETTINGS["accent"]
        ),
        "viz_3d": valid_viz_3d,
        "viz_circular": valid_viz_circular,
    }
