"""Load bundled package data in development and PyInstaller builds."""

from __future__ import annotations

import sys
from pathlib import Path


def data_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "eq_augs" / "data"
    return Path(__file__).resolve().parent / "data"


def assets_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "eq_augs" / "assets"
    return Path(__file__).resolve().parent / "assets"


def gui_dir() -> Path:
    return data_dir() / "gui"


def asset_path(filename: str) -> Path:
    return assets_dir() / filename


def gui_asset_path(filename: str) -> Path:
    return gui_dir() / filename


def read_data_text(filename: str) -> str:
    path = data_dir() / filename
    if not path.is_file():
        raise FileNotFoundError(f"Package data file not found: {filename} ({path})")
    return path.read_text(encoding="utf-8")
