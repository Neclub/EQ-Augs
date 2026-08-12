"""URL helpers for the pywebview HTML GUI."""

from __future__ import annotations

import base64

from eq_augs.package_data import asset_path, gui_asset_path


def file_url(path) -> str:
    return path.resolve().as_uri()


def setup_url() -> str:
    return file_url(gui_asset_path("setup.html"))


def eq_logo_data_uri(filename: str = "eq-icon.png") -> str:
    path = asset_path(filename)
    if not path.is_file():
        return ""
    data = path.read_bytes()
    encoded = base64.standard_b64encode(data).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def report_logo_data_uri() -> str:
    """Prefer the transparent circular report mark; fall back to the app icon."""
    uri = eq_logo_data_uri("eq-report-logo.png")
    return uri or eq_logo_data_uri("eq-icon.png")
