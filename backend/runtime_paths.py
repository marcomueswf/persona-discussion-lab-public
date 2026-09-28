from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


APP_DATA_FOLDER = "PersonaDiscussionLab"


def get_app_data_dir() -> Path:
    """Return the writable per-user directory used by packaged releases."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DATA_FOLDER
    return Path.home() / ".local" / "share" / APP_DATA_FOLDER


def get_runtime_file(filename: str) -> Path:
    """Return a writable data file, seeding it from bundled defaults once."""
    data_dir = get_app_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / filename
    if not target.exists():
        bundled_file = Path(__file__).resolve().parent / "data" / filename
        if bundled_file.exists():
            shutil.copy2(bundled_file, target)
    return target


def get_bundle_root() -> Path:
    """Return the source or PyInstaller extraction directory."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent