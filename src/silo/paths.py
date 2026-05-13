"""Shared filesystem paths."""
from __future__ import annotations

from pathlib import Path

from platformdirs import user_config_dir

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
CACHE_DIR = PROJECT_ROOT / ".cache"
REPORTS_DIR = PROJECT_ROOT / "reports"

USER_CONFIG_DIR = Path(user_config_dir("silo", appauthor=False))
GOOGLE_TOKEN_PATH = USER_CONFIG_DIR / "google_token.json"
