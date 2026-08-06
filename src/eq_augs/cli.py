"""CLI entry for EQ Augs Slot2 checker."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from eq_augs import __version__
from eq_augs.excel_export import write_workbook
from eq_augs.export_bundle import build_export_bundle
from eq_augs.html_export import html_path_for_workbook, write_html
from eq_augs.profiles import PROFILES


def _downloads_dir() -> Path:
    return Path.home() / "Downloads"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check equipped Slot2 type 7/8 augs against raidloot BiS."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Inventory dump file(s) or folder(s) containing *-Inventory.txt",
    )
    parser.add_argument(
        "--profile",
        choices=list(PROFILES),
        default="dex",
        help="Fallback stat profile when class cannot be detected (default: dex)",
    )
    parser.add_argument(
        "--artisans-prize",
        action="store_true",
        help="Mark Artisan's Prize as owned (Ear BiS)",
    )
    parser.add_argument(
        "--include-anniversary",
        action="store_true",
        help="Include anniversary Gem of Distant Echoes augs in recommendations",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output .xlsx path (default: Downloads/{Server}_Slot2_Augs.xlsx)",
    )
    parser.add_argument(
        "--format",
        choices=["excel", "html", "both"],
        default="both",
        help="Output format (default: both)",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the HTML report in the default browser",
    )
    parser.add_argument("--version", action="version", version=f"eq-augs {__version__}")
    args = parser.parse_args(argv)

    bundle = build_export_bundle(
        args.inputs,
        profile=args.profile,
        artisans_prize_owned=args.artisans_prize,
        include_anniversary=args.include_anniversary,
    )
    if not bundle.characters:
        print("No inventory dumps found or parsed.", file=sys.stderr)
        return 1

    for w in bundle.warnings:
        print(f"Warning: {w}", file=sys.stderr)

    server = bundle.server or "Team"
    out = args.output or (_downloads_dir() / f"{bundle.export_prefix or server}_Slot2_Augs.xlsx")
    out = Path(out)

    saved_xlsx = None
    saved_html = None
    if args.format in ("excel", "both"):
        saved_xlsx = write_workbook(bundle, out)
        print(saved_xlsx, file=sys.stderr)
    if args.format in ("html", "both"):
        html_target = html_path_for_workbook(out) if args.format == "both" else out.with_suffix(".html")
        if args.format == "html" and out.suffix.lower() == ".html":
            html_target = out
        saved_html = write_html(bundle, html_target)
        print(saved_html, file=sys.stderr)
        if args.open:
            webbrowser.open(saved_html.resolve().as_uri())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
