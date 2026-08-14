"""Tests for EQ Resource advanced-search catalog parsing."""

from __future__ import annotations

from pathlib import Path

from eq_augs.eqresource_search import (
    eqresource_search_payload,
    fetch_eqresource_catalog,
    parse_eqresource_search_html,
)
from eq_augs.raidloot import unique_by_lore_group

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SEARCH = FIXTURES / "eqresource_search_int_snip.html"

_MYSTIC_ITEM = """
<font size="+1"><b><center>Mystic's Gem of Unraveling Order<br><br></center></b></font>
Slot: Arms, Back, Chest, Ear, Face, Feet, Finger, Hands, Head, Legs, Neck, Shoulder, Waist, Wrist
<td>AC:<br>HP:<br>Mana:<br>End:<br></td>
<td>115<br>1470<br>2040<br>2040<br></td>
Lore Group: <a href="itemsearch.php?loregroup=Intellect or Might of Unraveling Order">Intellect or Might of Unraveling Order</a>
"""

_DEFENDER_ITEM = """
<font size="+1"><b><center>Defender's Gem of Unraveling Order<br><br></center></b></font>
Slot: Arms, Back, Chest, Ear, Face, Feet, Finger, Hands, Head, Legs, Neck, Shoulder, Waist, Wrist
<td>AC:<br>HP:<br>Mana:<br>End:<br></td>
<td>115<br>2040<br>1470<br>1470<br></td>
Lore Group: <a href="itemsearch.php?loregroup=Intellect or Might of Unraveling Order">Intellect or Might of Unraveling Order</a>
"""


def test_eqresource_search_payload_int_spell_damage():
    payload = eqresource_search_payload("int", augtype="7")
    assert payload["type"] == "augs"
    assert payload["augtype"] == "7"
    assert payload["augmentation"] == "1"
    assert payload["attrib1"] == "spelldamage"
    assert payload["attrib1range"] == "greater"
    assert payload["attrib1amt"] == "80"
    assert payload["attrib2"] == "hintel"
    assert payload["attrib3"] == "hdex"
    assert payload["attrib4"] == "hwis"


def test_parse_eqresource_search_html_stats():
    rows = parse_eqresource_search_html(SEARCH.read_text(encoding="utf-8"))
    by_id = {r.item_id: r for r in rows}
    assert set(by_id) >= {88785, 175573, 175571, 175572}
    mystic = by_id[175573]
    assert mystic.name.startswith("Mystic")
    assert mystic.stats.get("spell_damage") == 118
    assert mystic.stats.get("hint") == 61
    assert mystic.stats.get("hwis") == 61
    assert mystic.stats.get("ac") == 115
    assert mystic.stats.get("hp") == 1470
    defender = by_id[175571]
    assert defender.stats.get("spell_damage") == 111
    assert defender.stats.get("hp") == 2040


def test_eqresource_catalog_hydrates_lore_group():
    cat = fetch_eqresource_catalog(
        "int",
        html_override=SEARCH.read_text(encoding="utf-8"),
        item_html_by_id={175573: _MYSTIC_ITEM, 175571: _DEFENDER_ITEM},
        allow_network=False,
    )
    by_id = {a.item_id: a for a in cat.augs}
    assert by_id[175573].lore_group == "Intellect or Might of Unraveling Order"
    assert by_id[175571].lore_group == "Intellect or Might of Unraveling Order"
    assert by_id[175573].stats.get("spell_damage") == 118
    kept = unique_by_lore_group(
        [by_id[175573], by_id[175571], by_id[88785]]
    )
    assert [a.item_id for a in kept] == [175573, 88785]
