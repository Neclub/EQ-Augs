"""Tests for BiS comparison and Artisan's Prize checkbox."""

from __future__ import annotations

from pathlib import Path

from eq_augs.compare import (
    Slot2Comparison,
    assign_slot_recommendations,
    build_ideal_loadout,
    compare_character,
    recommend_for_slot,
    slot_stat_deltas,
    summarize_stat_deltas,
    upgrade_stat_delta_note,
)
from eq_augs.parser import InventoryData, InventoryItem, Slot2Aug, parse_inventory_file
from eq_augs.profiles import ARTISANS_PRIZE_ID, ARTISANS_PRIZE_NAME
from eq_augs.raidloot import (
    AugCandidate,
    CatalogResult,
    merge_shield_augs,
    parse_raidloot_html,
    parse_shield_html,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "raidloot_dex_sample.html"
SHIELD_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "raidloot_shield_snip.html"
EXAMPLES = Path(__file__).resolve().parents[1] / "Example" / "Inventory Dumps"


def _catalog() -> CatalogResult:
    html = FIXTURE.read_text(encoding="utf-8")
    augs = parse_raidloot_html(html, "dex")
    return CatalogResult(
        profile="dex",
        augs=augs,
        fetched_at="test",
        from_cache=False,
        url="http://test",
    )


def _catalog_with_shields() -> CatalogResult:
    result = _catalog()
    shields = parse_shield_html(SHIELD_FIXTURE.read_text(encoding="utf-8"), "dex")
    return CatalogResult(
        profile="dex",
        augs=merge_shield_augs(result.augs, shields),
        fetched_at="test",
        from_cache=False,
        url="http://test",
    )


def test_recommend_ear_without_prize():
    cat = _catalog().augs
    rec = recommend_for_slot("Ear-1", cat, artisans_prize_owned=False)
    assert rec is not None
    assert rec.item_id != ARTISANS_PRIZE_ID


def test_recommend_ear_with_prize():
    cat = _catalog().augs
    rec = recommend_for_slot("Ear-1", cat, artisans_prize_owned=True)
    assert rec is not None
    assert rec.item_id == ARTISANS_PRIZE_ID
    assert rec.name == ARTISANS_PRIZE_NAME


def test_recommend_charm_not_top_general():
    cat = _catalog().augs
    rec = recommend_for_slot("Charm", cat, artisans_prize_owned=False)
    assert rec is not None
    assert rec.item_id == 166898
    assert not any(a.item_id == 175572 and a.fits_gear_slot("Charm") for a in cat)


def test_compare_stablub_offline():
    data = parse_inventory_file(EXAMPLES / "Stablub_bristle-Inventory.txt")
    assert data is not None
    report = compare_character(
        data,
        _catalog(),
        artisans_prize_owned=False,
        profile="dex",
        fetch_eqr_augs=False,
    )
    by_slot = {c.gear_slot: c for c in report.comparisons}
    assert "Ear-1" in by_slot
    assert "Head" in by_slot
    # Never recommend a worse weighted rank than current when both are in catalog
    cat_by_id = {a.item_id: a for a in _catalog().augs}
    from eq_augs.weights import rank_key

    for cmp_ in report.comparisons:
        if cmp_.status != "upgrade" or cmp_.current_id is None or cmp_.recommended_id is None:
            continue
        cur = cat_by_id.get(cmp_.current_id)
        rec = cat_by_id.get(cmp_.recommended_id)
        if cur and rec:
            assert rank_key(rec, None, cmp_.gear_slot) <= rank_key(
                cur, None, cmp_.gear_slot
            ), (
                cmp_.gear_slot,
                cur.name,
                rec.name,
            )


def test_keeps_owned_ideal_aug_no_downgrade():
    cat = _catalog().augs
    slots = ["Head", "Feet", "Ear-1"]
    current = {
        "Head": Slot2Aug(
            gear_slot="Head",
            name="Mist-Filled Vial",
            item_id=175369,
        ),
        "Feet": Slot2Aug(gear_slot="Feet", name=None, item_id=None),
        "Ear-1": Slot2Aug(gear_slot="Ear-1", name=None, item_id=None),
    }
    assigned = assign_slot_recommendations(
        slots,
        cat,
        artisans_prize_owned=False,
        current_by_slot=current,
    )
    # Mist-Filled is ideal for some slot; keep it on Head (no downgrade).
    assert assigned["Head"] is not None
    assert assigned["Head"].item_id == 175369
    # Missing top (Acrobat's) goes to an empty hole, not replacing Mist-Filled.
    empty_recs = {
        assigned["Feet"].item_id if assigned["Feet"] else None,
        assigned["Ear-1"].item_id if assigned["Ear-1"] else None,
    }
    assert 175572 in empty_recs


def test_range_claims_bis_from_other_slot():
    cat = _catalog().augs
    # Joy of the Dancer is Range BiS; currently sitting on Head.
    slots = ["Head", "Range", "Charm", "Ear-1"]
    current = {
        "Head": Slot2Aug(
            gear_slot="Head",
            name="Joy of the Dancer",
            item_id=175169,
        ),
        "Range": Slot2Aug(gear_slot="Range", name=None, item_id=None),
        "Charm": Slot2Aug(gear_slot="Charm", name=None, item_id=None),
        "Ear-1": Slot2Aug(gear_slot="Ear-1", name=None, item_id=None),
    }
    assigned = assign_slot_recommendations(
        slots, cat, artisans_prize_owned=False, current_by_slot=current
    )
    assert assigned["Range"] is not None
    assert assigned["Range"].item_id == 175169
    assert assigned["Head"] is not None
    assert assigned["Head"].item_id != 175169

    data = InventoryData(
        character="Movelub",
        server="test",
        filepath="Movelub_test-Inventory.txt",
        items=[
            InventoryItem("Head", "Test Helm", 1, 1, 6),
            InventoryItem("Head-Slot2", "Joy of the Dancer", 175169, 1, 0),
            InventoryItem("Range", "Short Bow", 2, 1, 6),
            InventoryItem("Range-Slot1", "Empty", 0, 0, 0),
            InventoryItem("Range-Slot2", "Empty", 0, 0, 0),
            InventoryItem("Range-Slot3", "Empty", 0, 0, 0),
            InventoryItem("Range-Slot4", "Empty", 0, 0, 0),
            InventoryItem("Charm", "Test Charm", 3, 1, 6),
            InventoryItem("Charm-Slot2", "Empty", 0, 0, 0),
        ],
    )
    report = compare_character(
        data,
        _catalog(),
        artisans_prize_owned=False,
        profile="dex",
        fetch_eqr_augs=False,
    )
    by_slot = {c.gear_slot: c for c in report.comparisons}
    assert by_slot["Range"].recommended_id == 175169
    assert "Move from Head" in by_slot["Range"].note
    assert by_slot["Range"].move_from_slot == "Head"
    assert by_slot["Range"].recommended_owned is True
    assert "Move Joy of the Dancer to Range" in by_slot["Head"].note
    assert by_slot["Head"].recommended_id != 175169


def test_displaced_range_aug_moves_to_head_as_owned():
    """Better Range BiS frees the current Range aug for Head (move, not farm)."""
    better_range = AugCandidate(
        item_id=999001,
        name="Better Range Gem",
        profile="dex",
        focus_heroic=90,
        ac=200,
        hp=2000,
        atk=90,
        excluded_bases=frozenset({"Primary", "Secondary", "Ammo"}),
        source="test",
    )
    joy = AugCandidate(
        item_id=175169,
        name="Joy of the Dancer",
        profile="dex",
        focus_heroic=41,
        ac=143,
        hp=990,
        atk=65,
        excluded_bases=frozenset({"Primary", "Secondary", "Ammo"}),
        source="test",
    )
    catalog = [better_range, joy]
    slots = ["Head", "Range"]
    current = {
        "Range": Slot2Aug(
            gear_slot="Range",
            name="Joy of the Dancer",
            item_id=175169,
        ),
        "Head": Slot2Aug(gear_slot="Head", name=None, item_id=None),
    }
    assigned = assign_slot_recommendations(
        slots, catalog, artisans_prize_owned=False, current_by_slot=current
    )
    assert assigned["Range"] is not None
    assert assigned["Range"].item_id == 999001
    assert assigned["Head"] is not None
    assert assigned["Head"].item_id == 175169

    data = InventoryData(
        character="Rangelub",
        server="test",
        filepath="Rangelub_test-Inventory.txt",
        items=[
            InventoryItem("Head", "Test Helm", 1, 1, 6),
            InventoryItem("Head-Slot2", "Empty", 0, 0, 0),
            InventoryItem("Range", "Short Bow", 2, 1, 6),
            InventoryItem("Range-Slot1", "Empty", 0, 0, 0),
            InventoryItem("Range-Slot2", "Empty", 0, 0, 0),
            InventoryItem("Range-Slot3", "Empty", 0, 0, 0),
            InventoryItem("Range-Slot4", "Joy of the Dancer", 175169, 1, 0),
        ],
    )
    report = compare_character(
        data,
        CatalogResult(
            profile="dex",
            augs=catalog,
            fetched_at="test",
            from_cache=False,
            url="http://test",
        ),
        artisans_prize_owned=False,
        profile="dex",
        fetch_eqr_augs=False,
        type78_slot_by_parent_id={2: 4},
    )
    by_slot = {c.gear_slot: c for c in report.comparisons}
    assert by_slot["Range"].recommended_id == 999001
    assert by_slot["Range"].recommended_owned is False
    assert by_slot["Head"].recommended_id == 175169
    assert by_slot["Head"].move_from_slot == "Range"
    assert by_slot["Head"].recommended_owned is True
    assert "Move from Range" in by_slot["Head"].note

    from eq_augs.export_bundle import build_farm_list

    farm = build_farm_list([report], [])
    farm_ids = {e.item_id for e in farm}
    assert 999001 in farm_ids
    assert 175169 not in farm_ids


def test_charm_claims_bis_from_other_slot():
    cat = _catalog().augs
    # Unparalleled Finesse is Charm BiS in the sample catalog.
    slots = ["Head", "Charm", "Range"]
    current = {
        "Head": Slot2Aug(
            gear_slot="Head",
            name="Unparalleled Finesse Gem of Distant Echoes",
            item_id=166898,
        ),
        "Charm": Slot2Aug(gear_slot="Charm", name=None, item_id=None),
        "Range": Slot2Aug(gear_slot="Range", name=None, item_id=None),
    }
    assigned = assign_slot_recommendations(
        slots, cat, artisans_prize_owned=False, current_by_slot=current
    )
    assert assigned["Charm"] is not None
    assert assigned["Charm"].item_id == 166898
    assert assigned["Head"] is None or assigned["Head"].item_id != 166898


def test_ideal_loadout_assigns_range_and_charm_first():
    cat = _catalog().augs
    ideal = build_ideal_loadout(
        ["Head", "Feet", "Charm", "Range", "Ear-1"],
        cat,
        artisans_prize_owned=False,
    )
    assert ideal["Range"] is not None
    assert ideal["Range"].item_id == 175169  # Joy — fits Range
    assert ideal["Charm"] is not None
    assert ideal["Charm"].item_id == 166898  # Finesse — best remaining Charm fit
    assert ideal["Range"].item_id != ideal["Charm"].item_id


def test_only_recommends_missing_ideal_augs():
    cat = _catalog().augs
    ideal = build_ideal_loadout(
        ["Head", "Feet", "Charm", "Ear-1"],
        cat,
        artisans_prize_owned=False,
    )
    ideal_ids = {a.item_id for a in ideal.values() if a}
    # Own every ideal piece already (spread across slots).
    slots = list(ideal.keys())
    current = {}
    for slot, aug in ideal.items():
        if aug is None:
            current[slot] = Slot2Aug(gear_slot=slot, name=None, item_id=None)
        else:
            current[slot] = Slot2Aug(
                gear_slot=slot, name=aug.name, item_id=aug.item_id
            )
    assigned = assign_slot_recommendations(
        slots, cat, artisans_prize_owned=False, current_by_slot=current
    )
    for slot, pick in assigned.items():
        if pick is not None:
            assert pick.item_id in ideal_ids
        cur = current[slot]
        if cur.item_id:
            assert pick is not None and pick.item_id == cur.item_id


def test_equipped_aug_not_recommended_elsewhere_when_ideal():
    """Ideal-loadout piece on a general slot stays put (no general reshuffle)."""
    cat = _catalog().augs
    slots = ["Head", "Feet"]
    current = {
        "Head": Slot2Aug(
            gear_slot="Head",
            name="Acrobat's Gem of Unraveling Order",
            item_id=175572,
        ),
        "Feet": Slot2Aug(gear_slot="Feet", name=None, item_id=None),
    }
    assigned = assign_slot_recommendations(
        slots, cat, artisans_prize_owned=False, current_by_slot=current
    )
    assert assigned["Head"].item_id == 175572
    assert assigned["Feet"] is None or assigned["Feet"].item_id != 175572


def test_no_general_to_general_reshuffle_for_exact_homes():
    """Best owned set stays equipped; do not swap general holes to match ideal homes."""
    cat = _catalog().augs
    slots = ["Head", "Feet", "Range", "Charm"]
    current = {
        "Head": Slot2Aug(
            gear_slot="Head",
            name="Acrobat's Gem of Unraveling Order",
            item_id=175572,
        ),
        "Feet": Slot2Aug(gear_slot="Feet", name=None, item_id=None),
        "Range": Slot2Aug(gear_slot="Range", name=None, item_id=None),
        "Charm": Slot2Aug(gear_slot="Charm", name=None, item_id=None),
    }
    assigned = assign_slot_recommendations(
        slots, cat, artisans_prize_owned=False, current_by_slot=current
    )
    # Acrobat's is kept on Head; Mist fills the empty hole — both ideals equipped.
    assert assigned["Head"].item_id == 175572
    assert assigned["Feet"] is not None
    assert assigned["Feet"].item_id == 175369


def test_feet_priority_claims_bis_for_war():
    """WAR Feet is a priority hole: high-AC BiS is claimed before general slots."""
    cat = _catalog().augs
    slots = ["Head", "Arms", "Feet", "Range", "Charm"]
    ideal = build_ideal_loadout(
        slots, cat, artisans_prize_owned=False, class_abbr="WAR"
    )
    assert ideal["Range"].item_id == 175169
    # After Range/Charm, Feet claims next-best AC (Acrobat's), not Arms.
    assert ideal["Feet"].item_id == 175572
    assert ideal["Arms"] is None or ideal["Arms"].item_id != 175572

    current = {
        "Arms": Slot2Aug(
            gear_slot="Arms",
            name="Acrobat's Gem of Unraveling Order",
            item_id=175572,
        ),
        "Feet": Slot2Aug(gear_slot="Feet", name=None, item_id=None),
        "Head": Slot2Aug(gear_slot="Head", name=None, item_id=None),
        "Range": Slot2Aug(gear_slot="Range", name=None, item_id=None),
        "Charm": Slot2Aug(gear_slot="Charm", name=None, item_id=None),
    }
    assigned = assign_slot_recommendations(
        slots,
        cat,
        artisans_prize_owned=False,
        class_abbr="WAR",
        current_by_slot=current,
    )
    assert assigned["Feet"].item_id == 175572
    assert assigned["Arms"] is None or assigned["Arms"].item_id != 175572


def test_feet_not_priority_for_rog():
    """ROG Feet stays in the general pool (no high-AC priority claim)."""
    from eq_augs.slots import priority_aug_slots

    assert priority_aug_slots("ROG") == ("Range", "Charm")
    assert priority_aug_slots("WAR") == ("Range", "Charm", "Feet")

    cat = _catalog().augs
    slots = ["Head", "Arms", "Feet", "Range", "Charm"]
    ideal_rog = build_ideal_loadout(
        slots, cat, artisans_prize_owned=False, class_abbr="ROG"
    )
    # Without Feet priority, Arms (earlier in report order) can take Acrobat's.
    assert ideal_rog["Arms"].item_id == 175572


def test_feet_high_ac_for_war():
    cat = _catalog().augs
    default = recommend_for_slot("Feet", cat, artisans_prize_owned=False)
    assert default is not None
    assert default.item_id == 175572

    war = recommend_for_slot("Feet", cat, artisans_prize_owned=False, class_abbr="WAR")
    assert war is not None
    assert war.item_id == 175169
    assert war.ac >= default.ac


def test_feet_high_ac_not_for_rog():
    cat = _catalog().augs
    rog = recommend_for_slot("Feet", cat, artisans_prize_owned=False, class_abbr="ROG")
    assert rog is not None
    assert rog.item_id == 175572


def test_feet_high_ac_classes_mnk_rng_bst_brd():
    cat = _catalog().augs
    for cls in ("MNK", "RNG", "BST", "BRD"):
        rec = recommend_for_slot("Feet", cat, artisans_prize_owned=False, class_abbr=cls)
        assert rec is not None
        assert rec.item_id == 175169, cls


def test_primary_and_weapon_secondary_ignored():
    data = parse_inventory_file(EXAMPLES / "Stablub_bristle-Inventory.txt")
    assert data is not None
    report = compare_character(
        data,
        _catalog_with_shields(),
        artisans_prize_owned=False,
        profile="dex",
        fetch_eqr_augs=False,
    )
    by_slot = {c.gear_slot: c for c in report.comparisons}
    assert by_slot["Primary"].recommended_id is None
    assert "Primary weapons ignored" in by_slot["Primary"].note
    assert by_slot["Secondary"].recommended_id is None
    assert "Secondary weapons ignored" in by_slot["Secondary"].note


def test_shield_secondary_recommends_highest_ac():
    cat = _catalog_with_shields().augs
    rec = recommend_for_slot(
        "Secondary", cat, artisans_prize_owned=False, secondary_is_shield=True
    )
    assert rec is not None
    assert rec.shield_only is True
    assert rec.item_id == 175179
    assert recommend_for_slot(
        "Secondary", cat, artisans_prize_owned=False, secondary_is_shield=False
    ) is None


def test_slot_stat_deltas_and_summary_rollup():
    weaker = AugCandidate(
        item_id=1,
        name="Weak",
        profile="dex",
        focus_heroic=49,
        ac=95,
        hp=1417,
        atk=10,
        stats={
            "hdex": 49,
            "ac": 95,
            "hp": 1417,
            "atk": 10,
            "heal_amount": 5,
            "spell_damage": 0,
            "clairvoyance": 0,
        },
    )
    stronger = AugCandidate(
        item_id=2,
        name="Strong",
        profile="dex",
        focus_heroic=61,
        ac=115,
        hp=1750,
        atk=25,
        stats={
            "hdex": 61,
            "ac": 115,
            "hp": 1750,
            "atk": 25,
            "heal_amount": 8,
            "spell_damage": 12,
            "clairvoyance": 4,
        },
    )
    empty_gain = AugCandidate(
        item_id=3,
        name="Fill",
        profile="dex",
        focus_heroic=40,
        ac=100,
        hp=900,
        atk=5,
        stats={"hdex": 40, "ac": 100, "hp": 900, "atk": 5},
    )

    d_upgrade = slot_stat_deltas(weaker, stronger, "dex")
    assert d_upgrade["focus"] == 12
    assert d_upgrade["ac"] == 20
    assert d_upgrade["hp"] == 333
    assert d_upgrade["atk"] == 15
    assert d_upgrade["heal_amount"] == 3
    assert d_upgrade["spell_damage"] == 12
    assert d_upgrade["clairvoyance"] == 4

    d_empty = slot_stat_deltas(None, empty_gain, "dex")
    assert d_empty["focus"] == 40
    assert d_empty["ac"] == 100
    assert d_empty["hp"] == 900

    comps = [
        Slot2Comparison(
            gear_slot="Head",
            current_name="Weak",
            current_id=1,
            recommended_name="Strong",
            recommended_id=2,
            recommended_focus=61,
            status="upgrade",
            stat_deltas=d_upgrade,
        ),
        Slot2Comparison(
            gear_slot="Arms",
            current_name=None,
            current_id=None,
            recommended_name="Fill",
            recommended_id=3,
            recommended_focus=40,
            status="empty",
            stat_deltas=d_empty,
        ),
        Slot2Comparison(
            gear_slot="Legs",
            current_name="BiS",
            current_id=9,
            recommended_name="BiS",
            recommended_id=9,
            recommended_focus=70,
            status="bis",
            stat_deltas=None,
        ),
    ]
    totals, changed = summarize_stat_deltas(comps)
    assert changed == 2
    assert totals["focus"] == 52
    assert totals["ac"] == 120
    assert totals["hp"] == 1233
    assert totals["atk"] == 20
    assert totals["heal_amount"] == 3
    assert totals["spell_damage"] == 12
    assert totals["clairvoyance"] == 4


def test_upgrade_stat_delta_note_hint_label():
    weaker = AugCandidate(
        item_id=1,
        name="Weak",
        profile="int",
        focus_heroic=40,
        ac=90,
        hp=1000,
        stats={"hint": 40, "ac": 90, "hp": 1000},
    )
    stronger = AugCandidate(
        item_id=2,
        name="Strong",
        profile="int",
        focus_heroic=55,
        ac=100,
        hp=1200,
        stats={"hint": 55, "ac": 100, "hp": 1200},
    )
    note = upgrade_stat_delta_note(
        weaker, stronger, "Head", "WIZ", profile="int"
    )
    assert "HInt" in note
    assert "+15 HInt" in note
    assert "score" in note


def test_upgrade_stat_delta_note_hdex_primary():
    weaker = AugCandidate(
        item_id=1,
        name="Weak",
        profile="dex",
        focus_heroic=49,
        ac=95,
        hp=1417,
        stats={"hdex": 49, "ac": 95, "hp": 1417},
    )
    stronger = AugCandidate(
        item_id=2,
        name="Strong",
        profile="dex",
        focus_heroic=61,
        ac=115,
        hp=1750,
        stats={"hdex": 61, "ac": 115, "hp": 1750},
    )
    note = upgrade_stat_delta_note(weaker, stronger, "Head", "ROG")
    assert "score" in note
    assert "+12 HDex" in note
    assert "+333 HP" in note
    assert "+20 AC" in note


def test_upgrade_stat_delta_note_empty_and_ac_primary():
    stronger = AugCandidate(
        item_id=2,
        name="Strong",
        profile="dex",
        focus_heroic=41,
        ac=143,
        hp=990,
        stats={"hdex": 41, "ac": 143, "hp": 990},
    )
    note = upgrade_stat_delta_note(
        None, stronger, "Feet", "WAR", secondary_is_shield=False, profile="dex"
    )
    assert "score" in note
    assert "AC" in note


def test_upgrade_stat_delta_note_shield_secondary():
    shield = AugCandidate(
        item_id=175179,
        name="Shield Gem",
        profile="dex",
        focus_heroic=10,
        ac=200,
        hp=500,
        shield_only=True,
        stats={"ac": 200, "hp": 500, "hdex": 10},
    )
    note = upgrade_stat_delta_note(
        None, shield, "Secondary", "WAR", secondary_is_shield=True
    )
    assert "score" in note
    assert "+200 AC" in note
    assert "+500 HP" in note


def test_compare_upgrade_note_shows_stat_delta():
    data = InventoryData(
        character="Upgradelub",
        server="test",
        filepath="Upgradelub_test-Inventory.txt",
        items=[
            InventoryItem("Head", "Test Helm", 1, 1, 6),
            InventoryItem("Head-Slot2", "Unparalleled Finesse Gem of Distant Echoes", 166898, 1, 0),
        ],
    )
    report = compare_character(
        data,
        _catalog(),
        artisans_prize_owned=False,
        profile="dex",
        fetch_eqr_augs=False,
    )
    head = next(c for c in report.comparisons if c.gear_slot == "Head")
    assert head.status == "upgrade"
    assert "score" in head.note
    assert "+12 HDex" in head.note or "HDex" in head.note
    assert "+333 HP" in head.note
    assert "+20 AC" in head.note


def test_compare_shield_secondary_inventory():
    data = InventoryData(
        character="Shieldlub",
        server="test",
        filepath="Shieldlub_test-Inventory.txt",
        items=[
            InventoryItem("Head", "Test Helm", 1, 1, 6),
            InventoryItem("Head-Slot2", "Empty", 0, 0, 0),
            InventoryItem("Secondary", "Tower Shield of Rebellion", 173941, 1, 6),
            InventoryItem("Secondary-Slot1", "Empty", 0, 0, 0),
            InventoryItem("Secondary-Slot2", "Empty", 0, 0, 0),
        ],
    )
    report = compare_character(
        data,
        _catalog_with_shields(),
        artisans_prize_owned=False,
        profile="dex",
        fetch_eqr_augs=False,
    )
    by_slot = {c.gear_slot: c for c in report.comparisons}
    assert "Secondary" in by_slot
    sec = by_slot["Secondary"]
    assert sec.recommended_id == 175179
    assert sec.status == "empty"
    assert "Shield Only" in sec.note
    assert sec.note.startswith("+")
    assert "AC" in sec.note.split(";")[0]
