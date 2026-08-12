"""Pywebview HTML GUI entry point."""

from __future__ import annotations

import webview

from eq_augs import __version__
from eq_augs.package_data import asset_path
from eq_augs.web_api import WebApi
from eq_augs.web_bridge import setup_url


def main() -> None:
    api = WebApi()
    window = webview.create_window(
        f"EQ Augs — Slot2 Type 7/8 Checker v{__version__}",
        url=setup_url(),
        js_api=api,
        # Tall enough for Aug options + Advanced weights without clipping.
        width=920,
        height=780,
        min_size=(800, 700),
        background_color="#0b0e11",
    )
    api.bind_window(window)
    icon = asset_path("eq-icon.ico")
    start_kwargs: dict = {"debug": False}
    if icon.is_file():
        start_kwargs["icon"] = str(icon.resolve())
    webview.start(**start_kwargs)


if __name__ == "__main__":
    main()
