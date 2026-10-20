"""Configuration loader for Glaze."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any


def load_user_config() -> dict[str, Any]:
    """Loads optional user defaults from ~/.config/glaze/glaze.toml."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_config) if xdg_config else Path.home() / ".config"
    cfg_path = base / "glaze" / "glaze.toml"
    if cfg_path.is_file():
        try:
            with cfg_path.open("rb") as f:
                data = tomllib.load(f)
            return data.get("general", data) if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}
