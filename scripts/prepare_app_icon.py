"""Build packaged app icons from Icon/Icon.png (PNG + multi-size ICO)."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from prepare_report_logo import circularize

_ROOT = Path(__file__).resolve().parent.parent
_SOURCE = _ROOT / "Icon" / "Icon.png"
_ASSETS = _ROOT / "src" / "eq_augs" / "assets"
_PNG_SIZE = 256
_ICO_SIZES = (16, 32, 48, 64, 128, 256)


def prepare_icons(source: Path = _SOURCE, assets: Path = _ASSETS) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Icon source not found: {source}")
    assets.mkdir(parents=True, exist_ok=True)

    # Same circular transparent cutout as the HTML report logo.
    master = circularize(Image.open(source), size=_PNG_SIZE)
    png_path = assets / "eq-icon.png"
    master.save(png_path, format="PNG", optimize=True)

    ico_path = assets / "eq-icon.ico"
    master.save(ico_path, format="ICO", sizes=[(size, size) for size in _ICO_SIZES])
    print(f"Wrote {png_path.relative_to(_ROOT)} ({png_path.stat().st_size} bytes)")
    print(f"Wrote {ico_path.relative_to(_ROOT)} ({ico_path.stat().st_size} bytes)")


def main() -> int:
    prepare_icons()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — CLI entrypoint
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
