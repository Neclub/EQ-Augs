"""URL helpers for the pywebview HTML GUI."""

from __future__ import annotations

import base64

from eq_augs.package_data import asset_path, gui_asset_path


def file_url(path) -> str:
    return path.resolve().as_uri()


def setup_url() -> str:
    return file_url(gui_asset_path("setup.html"))


def eq_logo_data_uri() -> str:
    path = asset_path("eq-icon.png")
    if not path.is_file():
        return ""
    data = path.read_bytes()
    encoded = base64.standard_b64encode(data).decode("ascii")
    return f"data:image/png;base64,{encoded}"
