"""Tests for determinate generate progress reporting."""

from __future__ import annotations

from pathlib import Path

from eq_augs.export_bundle import build_export_bundle

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "raidloot_dex_sample.html"


def test_build_export_bundle_progress_is_monotonic(tmp_path: Path):
    inv = tmp_path / "Proglub_test-ROG-Inventory.txt"
    inv.write_text(
        "Location\tName\tID\tCount\tSlots\n"
        "Head\tTest Helm\t1\t1\t6\n"
        "Head-Slot2\tEmpty\t0\t0\t0\n"
        "Charm\tTest Charm\t2\t1\t6\n"
        "Charm-Slot2\tEmpty\t0\t0\t0\n",
        encoding="utf-8",
    )
    html = FIXTURE.read_text(encoding="utf-8")
    events: list[dict] = []

    bundle = build_export_bundle(
        [inv],
        catalog_html=html,
        fetch_eqr_augs=False,
        fetch_chest_class=False,
        fetch_expansions=False,
        include_anniversary=False,
        type78_slot_by_parent_id={1: 2, 2: 2},
        on_progress=events.append,
    )

    assert bundle.characters
    assert events
    assert all("message" in e and "fraction" in e for e in events)
    fractions = [float(e["fraction"]) for e in events]
    assert fractions[0] >= 0.0
    assert fractions[-1] == 0.95
    assert all(0.0 <= f <= 1.0 for f in fractions)
    assert all(a <= b for a, b in zip(fractions, fractions[1:]))
