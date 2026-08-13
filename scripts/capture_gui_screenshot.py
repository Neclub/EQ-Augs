"""Capture the EQ Augs setup window into docs/images/gui-setup.png."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import webview
from PIL import ImageGrab

from eq_augs import __version__
from eq_augs.package_data import asset_path
from eq_augs.web_api import WebApi
from eq_augs.web_bridge import setup_url

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "docs" / "images" / "gui-setup.png"
_TITLE = f"EQ Augs — Slot2 Type 7/8 Checker v{__version__}"


def _find_window_rect(title: str) -> tuple[int, int, int, int] | None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        # Partial match fallback.
        matches: list[int] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def enum_proc(h, _lp):  # type: ignore[misc]
            length = user32.GetWindowTextLengthW(h)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(h, buf, length + 1)
            if buf.value.startswith("EQ Augs"):
                matches.append(h)
            return True

        user32.EnumWindows(enum_proc, 0)
        if not matches:
            return None
        hwnd = matches[0]

    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    user32.SetForegroundWindow(hwnd)
    return (rect.left, rect.top, rect.right, rect.bottom)


def _capture_after_ready(window: webview.Window) -> None:
    # Wait for page + logo data URI to paint.
    time.sleep(2.5)
    bbox = None
    for _ in range(20):
        bbox = _find_window_rect(_TITLE)
        if bbox:
            break
        time.sleep(0.25)
    if not bbox:
        print("error: could not locate EQ Augs window", file=sys.stderr)
        window.destroy()
        return

    # Brief settle after focus.
    time.sleep(0.4)
    shot = ImageGrab.grab(bbox=bbox, all_screens=True)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    shot.save(_OUT, format="PNG", optimize=True)
    print(f"Wrote {_OUT.relative_to(_ROOT)} ({shot.size[0]}x{shot.size[1]}, {_OUT.stat().st_size} bytes)")
    window.destroy()


def main() -> int:
    api = WebApi()
    window = webview.create_window(
        _TITLE,
        url=setup_url(),
        js_api=api,
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

    threading.Thread(target=_capture_after_ready, args=(window,), daemon=True).start()
    webview.start(**start_kwargs)
    return 0 if _OUT.is_file() else 1


if __name__ == "__main__":
    raise SystemExit(main())
