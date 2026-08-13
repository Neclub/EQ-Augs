"""Prepare a transparent circular report logo from generated/source art."""

from __future__ import annotations

import math
import sys
from collections import deque
from pathlib import Path

from PIL import Image

_ROOT = Path(__file__).resolve().parent.parent
_ASSETS = _ROOT / "src" / "eq_augs" / "assets"
_DEFAULT_SOURCE = _ROOT / "Icon" / "report-logo-source.png"
_OUTPUT = _ASSETS / "eq-report-logo.png"
_SIZE = 384


def _luma(r: int, g: int, b: int) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _is_plate(r: int, g: int, b: int, a: int) -> bool:
    """White / light-gray studio plate (not the dark crest interior)."""
    if a < 8:
        return True
    luma = _luma(r, g, b)
    spread = max(r, g, b) - min(r, g, b)
    # Near-white / light gray only — leave charcoal crest fill alone.
    if luma >= 200 and spread <= 28:
        return True
    if luma <= 22 and spread <= 18:
        return True
    return False


def _knockout_plate(img: Image.Image) -> Image.Image:
    """Flood-fill backdrop from the edges (keeps gem highlights intact)."""
    out = img.convert("RGBA")
    w, h = out.size
    px = out.load()
    visited = [[False] * w for _ in range(h)]
    q: deque[tuple[int, int]] = deque()

    seeds: list[tuple[int, int]] = [
        (0, 0),
        (w - 1, 0),
        (0, h - 1),
        (w - 1, h - 1),
        (w // 2, 0),
        (w // 2, h - 1),
        (0, h // 2),
        (w - 1, h // 2),
    ]
    step = max(1, min(w, h) // 40)
    for x in range(0, w, step):
        seeds.append((x, 0))
        seeds.append((x, h - 1))
    for y in range(0, h, step):
        seeds.append((0, y))
        seeds.append((w - 1, y))

    for seed in seeds:
        q.append(seed)

    while q:
        x, y = q.popleft()
        if x < 0 or y < 0 or x >= w or y >= h or visited[y][x]:
            continue
        visited[y][x] = True
        r, g, b, a = px[x, y]
        if not _is_plate(r, g, b, a):
            continue
        px[x, y] = (0, 0, 0, 0)
        for nx, ny in (
            (x + 1, y),
            (x - 1, y),
            (x, y + 1),
            (x, y - 1),
            (x + 1, y + 1),
            (x - 1, y - 1),
            (x + 1, y - 1),
            (x - 1, y + 1),
        ):
            q.append((nx, ny))
    return out


def _is_fringe_pixel(r: int, g: int, b: int, a: int) -> bool:
    """Light desaturated edge halo — not gold/purple crest paint."""
    if a < 8:
        return True
    luma = _luma(r, g, b)
    spread = max(r, g, b) - min(r, g, b)
    # White / gray cutout halo
    if luma >= 95 and spread <= 40:
        return True
    # Pale muddy anti-alias from a light backdrop
    if luma >= 140 and spread <= 55 and min(r, g, b) >= 110:
        return True
    return False


def _scrub_light_fringe(img: Image.Image, passes: int = 4) -> Image.Image:
    """Remove light halo pixels hugging transparent edges (keeps gold/purple)."""
    out = img.convert("RGBA")
    w, h = out.size
    for _ in range(passes):
        px = out.load()
        doomed: list[tuple[int, int]] = []
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a == 0 or not _is_fringe_pixel(r, g, b, a):
                    continue
                for ny in (y - 1, y, y + 1):
                    for nx in (x - 1, x, x + 1):
                        if nx == x and ny == y:
                            continue
                        if 0 <= nx < w and 0 <= ny < h and px[nx, ny][3] == 0:
                            doomed.append((x, y))
                            break
                    else:
                        continue
                    break
        for x, y in doomed:
            px[x, y] = (0, 0, 0, 0)
    return out


def with_solid_disc(
    crest: Image.Image,
    *,
    fill: tuple[int, int, int, int] = (22, 24, 28, 255),
    scale: float = 0.96,
) -> Image.Image:
    """Opaque circular backing under the crest (inset so it stays under the gold rim)."""
    from PIL import ImageDraw

    size = crest.size[0]
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    disc = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(disc)
    margin = max(1, int(size * (1.0 - scale) / 2.0))
    draw.ellipse(
        [margin, margin, size - 1 - margin, size - 1 - margin],
        fill=fill,
    )
    out = Image.alpha_composite(out, disc)
    out = Image.alpha_composite(out, crest.convert("RGBA"))
    # Final pass: kill any remaining light halo outside the badge.
    return _scrub_light_fringe(out, passes=3)


def circularize(im: Image.Image, size: int = _SIZE) -> Image.Image:
    """Square-crop, knock out light plate, circular mask, opaque crest disc."""
    img = im.convert("RGBA")
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    square = img.crop((left, top, left + side, top + side)).resize(
        (size, size), Image.Resampling.LANCZOS
    )
    square = _knockout_plate(square)

    pixels = square.load()
    cx = cy = (size - 1) / 2.0
    radius = size * 0.498
    for y in range(size):
        for x in range(size):
            r, g, b, a = pixels[x, y]
            dist = math.hypot(x - cx, y - cy)
            # Hard cut outside the badge — no soft white blend band.
            if dist > radius:
                pixels[x, y] = (0, 0, 0, 0)
                continue
            if a == 0 or _is_fringe_pixel(r, g, b, a) and dist > radius * 0.90:
                pixels[x, y] = (0, 0, 0, 0)
                continue
            if _is_plate(r, g, b, a) and dist > radius * 0.88:
                pixels[x, y] = (0, 0, 0, 0)

    crest = _scrub_light_fringe(square, passes=5)
    return with_solid_disc(crest)


def prepare_report_logo(
    source: Path | None = None,
    output: Path = _OUTPUT,
    size: int = _SIZE,
) -> Path:
    src = source or _DEFAULT_SOURCE
    if not src.is_file():
        src = _ASSETS / "eq-icon.png"
    if not src.is_file():
        raise FileNotFoundError(f"Report logo source not found: {src}")

    output.parent.mkdir(parents=True, exist_ok=True)
    logo = circularize(Image.open(src), size=size)
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
