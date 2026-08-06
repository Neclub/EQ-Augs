"""Tests for raidloot slot-restriction parsing and HTML catalog parse."""

from __future__ import annotations

from pathlib import Path

from eq_augs.raidloot import (
    augs_for_slot,
    merge_shield_augs,
    parse_raidloot_html,
    parse_shield_html,
    parse_slot_restrictions,
)
from eq_augs.profiles import ARTISANS_PRIZE_ID

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "raidloot_dex_sample.html"
SHIELD_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "raidloot_shield_snip.html"


def test_parse_all_except_charm_range():
    excluded, allowed, ear_only = parse_slot_restrictions(
        "All except Charm, Range, Primary, Secondary, Ammo"
    )
    assert ear_only is False
    assert allowed == frozenset()
    assert excluded == frozenset({"Charm", "Range", "Primary", "Secondary", "Ammo"})


def test_parse_fits_charm_and_range():
    excluded, allowed, ear_only = parse_slot_restrictions(
        "All except Primary, Secondary, Ammo"
    )
    assert "Charm" not in excluded
    assert "Range" not in excluded


def test_parse_ear_only():
    excluded, allowed, ear_only = parse_slot_restrictions("Ear")
    assert ear_only is True
    assert allowed == frozenset({"Ear"})


def test_parse_except_range_only_fits_charm():
    excluded, _, _ = parse_slot_restrictions(
        "All except Range, Primary, Secondary, Ammo"
    )
    assert "Range" in excluded
    assert "Charm" not in excluded


def test_parse_html_fixture():
    html = FIXTURE.read_text(encoding="utf-8")
    augs = parse_raidloot_html(html, "dex")
    by_id = {a.item_id: a for a in augs}
    assert ARTISANS_PRIZE_ID in by_id
    assert by_id[ARTISANS_PRIZE_ID].ear_only is True
    assert by_id[175572].excluded_bases >= frozenset({"Charm", "Range"})
    assert "Charm" not in by_id[175169].excluded_bases  # Joy of the Dancer fits Charm
    assert "Range" not in by_id[175169].excluded_bases
    assert by_id[175572].stats.get("hdex") == 61
    assert by_id[175572].stats.get("ac") == 115
    assert by_id[175572].stats.get("hp") == 1750
    assert by_id[175572].stats.get("atk") == 68
    assert by_id[ARTISANS_PRIZE_ID].stats.get("hdex") == 150


def test_parse_live_style_detail_divs():
    html = (
        Path(__file__).resolve().parent / "fixtures" / "raidloot_dex_live_snippet.html"
    ).read_text(encoding="utf-8")
    augs = parse_raidloot_html(html, "dex")
    by_id = {a.item_id: a for a in augs}
    assert 175572 in by_id
    assert by_id[175572].name.startswith("Acrobat")
    assert by_id[175572].focus_heroic == 61
    assert by_id[175572].ac == 115
    assert by_id[175572].lore is True
    assert "Charm" in by_id[175572].excluded_bases
    assert "Range" in by_id[175572].excluded_bases


def test_augs_for_charm_excludes_common_tops():
    html = FIXTURE.read_text(encoding="utf-8")
    augs = parse_raidloot_html(html, "dex")
    charm = augs_for_slot(augs, "Charm")
    ids = {a.item_id for a in charm}
    assert 175572 not in ids  # Acrobat's excludes Charm
    assert 175169 in ids  # Joy of the Dancer fits
    assert 166898 in ids  # Finesse gem excludes Range only — fits Charm


def test_augs_for_range():
    html = FIXTURE.read_text(encoding="utf-8")
    augs = parse_raidloot_html(html, "dex")
    range_augs = augs_for_slot(augs, "Range")
    ids = {a.item_id for a in range_augs}
    assert 175572 not in ids
    assert 166898 not in ids  # excludes Range
    assert 175169 in ids


def test_parse_secondary_slot_only():
    excluded, allowed, ear_only = parse_slot_restrictions("Secondary")
    assert ear_only is False
    assert allowed == frozenset({"Secondary"})
    assert excluded == frozenset()


def test_parse_shield_html_fixture():
    html = SHIELD_FIXTURE.read_text(encoding="utf-8")
    augs = parse_shield_html(html, "dex")
    assert augs
    assert all(a.shield_only for a in augs)
    assert all(a.fits_gear_slot("Secondary") for a in augs)
    assert all(not a.fits_gear_slot("Head") for a in augs)
    by_id = {a.item_id: a for a in augs}
    assert 175179 in by_id
    assert by_id[175179].name.startswith("Votive")
    assert by_id[175179].ac == 113


def test_merge_shield_augs_into_catalog():
    dex = parse_raidloot_html(FIXTURE.read_text(encoding="utf-8"), "dex")
    shields = parse_shield_html(SHIELD_FIXTURE.read_text(encoding="utf-8"), "dex")
    merged = merge_shield_augs(dex, shields)
    assert any(a.shield_only and a.item_id == 175179 for a in merged)
    # Shield augs must not appear as fits for Head
    head_ids = {a.item_id for a in augs_for_slot(merged, "Head")}
    assert 175179 not in head_ids
    sec = augs_for_slot(merged, "Secondary")
    assert any(a.item_id == 175179 and a.shield_only for a in sec)
