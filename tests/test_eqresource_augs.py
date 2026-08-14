"""Tests for EQ Resource aug stat fallback."""

from __future__ import annotations

from pathlib import Path

from eq_augs.compare import compare_character
from eq_augs.eqresource_augs import (
    parse_eqresource_aug_html,
    parse_eqresource_lore_group,
    parse_expansion_from_eqr_html,
    resolve_item_expansions,
)
from eq_augs.parser import InventoryData, InventoryItem
from eq_augs.raidloot import CatalogResult, parse_raidloot_html

FIXTURES = Path(__file__).resolve().parent / "fixtures"
RAIDLOOT = FIXTURES / "raidloot_dex_sample.html"


def _catalog() -> CatalogResult:
    augs = parse_raidloot_html(RAIDLOOT.read_text(encoding="utf-8"), "dex")
    return CatalogResult(
        profile="dex",
        augs=augs,
        fetched_at="test",
        from_cache=False,
        url="http://test",
    )


def test_parse_eqresource_aug_acrobat_dex():
    html = (FIXTURES / "eqresource_aug_175572.html").read_text(encoding="utf-8")
    aug = parse_eqresource_aug_html(html, "dex", item_id=175572)
    assert aug is not None
    assert aug.name.startswith("Acrobat")
    assert aug.focus_heroic == 61
    assert aug.ac == 115
    assert aug.hp == 1750
    assert aug.atk == 68
    assert aug.stats.get("hdex") == 61
    assert aug.stats.get("mana") == 1750
    assert aug.stats.get("spell_damage") == 114
    assert aug.stats.get("heal_amount") == 108
    assert aug.stats.get("clairvoyance") == 139
    assert "Head" in aug.allowed_bases
    assert "Charm" not in aug.allowed_bases
    assert "Range" not in aug.allowed_bases


def test_parse_eqresource_aug_phantasmal_no_dex_focus():
    html = (FIXTURES / "eqresource_aug_169570.html").read_text(encoding="utf-8")
    aug = parse_eqresource_aug_html(html, "dex", item_id=169570)
    assert aug is not None
    assert "Vigor" in aug.name
    assert aug.focus_heroic == 0  # STR/STA gem, not DEX
    assert aug.ac == 85
    assert aug.hp == 1460


def test_parse_eqresource_joy_fits_charm_range():
    html = (FIXTURES / "eqresource_aug_175169.html").read_text(encoding="utf-8")
    aug = parse_eqresource_aug_html(html, "dex", item_id=175169)
    assert aug is not None
    assert "Charm" in aug.allowed_bases
    assert "Range" in aug.allowed_bases


def test_unknown_aug_compared_via_eqresource():
    html = (FIXTURES / "eqresource_aug_169570.html").read_text(encoding="utf-8")
    data = InventoryData(
        character="Eqrlub",
        server="test",
        filepath="Eqrlub_test-Inventory.txt",
        items=[
            InventoryItem("Arms", "Test Arms", 1, 1, 6),
            InventoryItem(
                "Arms-Slot2",
                "Phantasmal Luclinite Gem of Vigor",
                169570,
                1,
                0,
            ),
        ],
    )
    report = compare_character(
        data,
        _catalog(),
        artisans_prize_owned=False,
        profile="dex",
        fetch_eqr_augs=False,
        eqr_aug_html_by_id={169570: html},
    )
    arms = next(c for c in report.comparisons if c.gear_slot == "Arms")
    assert arms.status == "upgrade"
    assert arms.recommended_id == 175572
    assert "stats via EQ Resource" not in arms.note
    # 61 HDex - 0 from Phantasmal on dex profile
    assert "+61 HDex" in arms.note
    assert "not in raidloot catalog" not in arms.note


def test_parse_expansion_from_fixtures():
    sor = (FIXTURES / "eqresource_aug_175169.html").read_text(encoding="utf-8")
    nos = (FIXTURES / "eqresource_aug_169570.html").read_text(encoding="utf-8")
    tob = (FIXTURES / "eqresource_chest_173849_mnk.html").read_text(encoding="utf-8")
    assert parse_expansion_from_eqr_html(sor) == "Shattering of Ro"
    assert parse_expansion_from_eqr_html(nos) == "Night of Shadows"
    assert parse_expansion_from_eqr_html(tob) == "The Outer Brood"


def test_resolve_item_expansions_from_overrides():
    html = (FIXTURES / "eqresource_aug_175169.html").read_text(encoding="utf-8")
    result = resolve_item_expansions(
        [175169, 999],
        html_overrides={175169: html},
        allow_network=False,
    )
    assert result[175169] == "Shattering of Ro"
    assert 999 not in result


def test_recommended_owned_when_aug_in_bags():
    """Recommended upgrade present in bags counts as owned (not farm)."""
    html = (FIXTURES / "eqresource_aug_169570.html").read_text(encoding="utf-8")
    data = InventoryData(
        character="Baglub",
        server="test",
        filepath="Baglub_test-Inventory.txt",
        items=[
            InventoryItem("Arms", "Test Arms", 1, 1, 6),
            InventoryItem(
                "Arms-Slot2",
                "Phantasmal Luclinite Gem of Vigor",
                169570,
                1,
                0,
            ),
            InventoryItem("General 1-Slot1", "Acrobat's Gem of Uprising", 175572, 1, 0),
        ],
    )
    report = compare_character(
        data,
        _catalog(),
        artisans_prize_owned=False,
        profile="dex",
        fetch_eqr_augs=False,
        eqr_aug_html_by_id={169570: html},
    )
    arms = next(c for c in report.comparisons if c.gear_slot == "Arms")
    assert arms.status == "upgrade"
    assert arms.recommended_id == 175572
    assert arms.recommended_owned is True
    assert 175572 in report.owned_item_ids


def test_recommended_not_owned_when_missing_from_inventory():
    html = (FIXTURES / "eqresource_aug_169570.html").read_text(encoding="utf-8")
    data = InventoryData(
        character="Needlub",
        server="test",
        filepath="Needlub_test-Inventory.txt",
        items=[
            InventoryItem("Arms", "Test Arms", 1, 1, 6),
            InventoryItem(
                "Arms-Slot2",
                "Phantasmal Luclinite Gem of Vigor",
                169570,
                1,
                0,
            ),
        ],
    )
    report = compare_character(
        data,
        _catalog(),
        artisans_prize_owned=False,
        profile="dex",
        fetch_eqr_augs=False,
        eqr_aug_html_by_id={169570: html},
    )
    arms = next(c for c in report.comparisons if c.gear_slot == "Arms")
    assert arms.recommended_id == 175572
    assert arms.recommended_owned is False
    assert 175572 not in report.owned_item_ids


def test_parse_eqresource_lore_group_name():
    snippet = (
        'Lore Group: <a href="itemsearch.php?loregroup=Intellect or Might of '
        'Unraveling Order">Intellect or Might of Unraveling Order</a>'
    )
    assert (
        parse_eqresource_lore_group(snippet)
        == "Intellect or Might of Unraveling Order"
    )
    encoded = (
        'Lore Group: <a href="itemsearch.php?loregroup=Intellect+or+Might+'
        'of+Unraveling+Order">Intellect or Might of Unraveling Order</a>'
    )
    assert (
        parse_eqresource_lore_group(encoded)
        == "Intellect or Might of Unraveling Order"
    )
    html = """
    <font size="+1"><b><center>Mystic's Gem of Unraveling Order<br><br></center></b></font>
    Slot: Arms, Back, Chest, Ear, Face, Feet, Finger, Hands, Head
    <td>AC:<br>HP:<br>Mana:<br>End:<br></td>
    <td>115<br>1470<br>2040<br>2040<br></td>
    Lore Group: <a href="itemsearch.php?loregroup=Intellect or Might of Unraveling Order">Intellect or Might of Unraveling Order</a>
    """
    aug = parse_eqresource_aug_html(html, "int", item_id=175573)
    assert aug is not None
    assert aug.lore_group == "Intellect or Might of Unraveling Order"
