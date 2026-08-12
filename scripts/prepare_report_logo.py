"""Prepare a transparent circular report logo from generated/source art."""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image

_ROOT = Path(__file__).resolve().parent.parent
_ASSETS = _ROOT / "src" / "eq_augs" / "assets"
_DEFAULT_SOURCE = _ROOT / "Icon" / "report-logo-source.png"
_OUTPUT = _ASSETS / "eq-report-logo.png"
_SIZE = 256


def _circularize(im: Image.Image, size: int = _SIZE) -> Image.Image:
    """Square-crop, resize, and apply a soft circular alpha mask."""
    img = im.convert("RGBA")
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    square = img.crop((left, top, left + side, top + side)).resize(
        (size, size), Image.Resampling.LANCZOS
    )

    # Knock out near-black backdrop that sits outside the emblem glow.
    pixels = square.load()
    cx = cy = (size - 1) / 2.0
    radius = size * 0.48
    feather = size * 0.03
    for y in range(size):
        for x in range(size):
            r, g, b, a = pixels[x, y]
            dist = math.hypot(x - cx, y - cy)
            if dist > radius + feather:
                pixels[x, y] = (r, g, b, 0)
                continue
            if dist > radius:
                t = 1.0 - (dist - radius) / feather
                pixels[x, y] = (r, g, b, max(0, min(255, int(a * t))))
                continue
            # Inside circle: clear leftover dark square plate near the rim.
            luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
            if luma < 28 and dist > radius * 0.82:
                pixels[x, y] = (r, g, b, 0)
    return square


def prepare_report_logo(
    source: Path | None = None,
    output: Path = _OUTPUT,
) -> Path:
    src = source or _DEFAULT_SOURCE
    if not src.is_file():
        # Fall back to packaged app icon if generated art is missing.
        src = _ASSETS / "eq-icon.png"
    if not src.is_file():
        raise FileNotFoundError(f"Report logo source not found: {src}")

    output.parent.mkdir(parents=True, exist_ok=True)
    logo = _circularize(Image.open(src))
    logo.save(output, format="PNG", optimize=True)
    print(f"Wrote {output} ({output.stat().st_size} bytes)")
    return output


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    source = Path(args[0]) if args else None
    prepare_report_logo(source=source)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — CLI entrypoint
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
