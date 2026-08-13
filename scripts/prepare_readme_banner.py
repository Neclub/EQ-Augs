"""Build docs/images/eq-augs-banner.jpg from the remade Icon/Icon.png crest."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from prepare_report_logo import circularize

_ROOT = Path(__file__).resolve().parent.parent
_SOURCE = _ROOT / "Icon" / "Icon.png"
_OUT = _ROOT / "docs" / "images" / "eq-augs-banner.jpg"
_WIDTH = 1280
_HEIGHT = 420
_CREST_SIZE = 340


def _gradient_bg(width: int, height: int) -> Image.Image:
    """Dark EQ Augs chrome gradient with a soft purple vignette."""
    # Build a small gradient then upscale for speed.
    sw, sh = 160, 53
    base = Image.new("RGB", (sw, sh))
    px = base.load()
    for y in range(sh):
        t = y / max(1, sh - 1)
        r = int(11 + (21 - 11) * t)
        g = int(14 + (26 - 14) * t)
        b = int(17 + (34 - 17) * t)
        for x in range(sw):
            cx, cy = sw * 0.5, sh * 0.52
            dx = (x - cx) / (sw * 0.28)
            dy = (y - cy) / (sh * 0.55)
            glow = max(0.0, 1.0 - (dx * dx + dy * dy))
            glow *= glow
            px[x, y] = (
                min(255, int(r + 28 * glow)),
                min(255, int(g + 12 * glow)),
                min(255, int(b + 48 * glow)),
            )
    return base.resize((width, height), Image.Resampling.LANCZOS)


def prepare_banner(
    source: Path = _SOURCE,
    output: Path = _OUT,
) -> Path:
    if not source.is_file():
        raise FileNotFoundError(f"Icon source not found: {source}")

    crest = circularize(Image.open(source), size=_CREST_SIZE)
    # Soft drop shadow under the crest.
    shadow = Image.new("RGBA", crest.size, (0, 0, 0, 0))
    alpha = crest.split()[-1]
    shadow_layer = Image.new("RGBA", crest.size, (0, 0, 0, 160))
    shadow_layer.putalpha(alpha)
    shadow = shadow_layer.filter(ImageFilter.GaussianBlur(18))

    canvas = _gradient_bg(_WIDTH, _HEIGHT).convert("RGBA")
    x = (_WIDTH - _CREST_SIZE) // 2
    y = (_HEIGHT - _CREST_SIZE) // 2 + 8
    canvas.paste(shadow, (x + 6, y + 14), shadow)
    canvas.paste(crest, (x, y), crest)

    output.parent.mkdir(parents=True, exist_ok=True)
    rgb = canvas.convert("RGB")
    rgb.save(output, format="JPEG", quality=90, optimize=True)
    # Keep Icon/banner.png as the high-quality source companion.
    icon_banner = _ROOT / "Icon" / "banner.png"
    rgb.save(icon_banner, format="PNG", optimize=True)
    print(f"Wrote {output.relative_to(_ROOT)} ({output.stat().st_size} bytes)")
    print(f"Wrote {icon_banner.relative_to(_ROOT)} ({icon_banner.stat().st_size} bytes)")
    return output


def main() -> int:
    prepare_banner()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — CLI entrypoint
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
