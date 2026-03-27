"""Scanner configuration — loads from config.json next to the executable."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict


def _config_dir() -> str:
    """Return the directory containing the running script or frozen exe."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class ScannerConfig:
    scanner_id: str = "MAIN_ENTRANCE"
    api_base_url: str = "https://your-app.railway.app"
    api_key: str = ""
    qr_selfie_enabled: bool = True
    webcam_index: int = 0
    offline_cache_path: str = "./offline_cache.enc"


_CONFIG_PATH = os.path.join(_config_dir(), "config.json")


def load_config() -> ScannerConfig:
    """Load config from disk, creating defaults if missing."""
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "r") as f:
            data = json.load(f)
        return ScannerConfig(**{k: v for k, v in data.items() if k in ScannerConfig.__dataclass_fields__})
    cfg = ScannerConfig()
    save_config(cfg)
    return cfg


def save_config(config: ScannerConfig) -> None:
    """Persist config to disk."""
    with open(_CONFIG_PATH, "w") as f:
        json.dump(asdict(config), f, indent=2)
