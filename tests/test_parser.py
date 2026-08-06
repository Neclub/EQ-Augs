"""Tests for inventory Slot2 extraction."""

from __future__ import annotations

from pathlib import Path

from eq_augs.parser import (
    collect_owned_item_ids,
    discover_inventory_files,
    extract_slot2_augs,
    parent_name_is_shield,
    parse_inventory_file,
    parse_inventory_filename,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "Example" / "Inventory Dumps"


def test_parse_filename_basic():
    char, server, cls = parse_inventory_filename("Stablub_bristle-Inventory.txt")
    assert char == "Stablub"
    assert server == "bristle"
    assert cls is None


def test_parse_filename_with_class():
    char, server, cls = parse_inventory_filename("Bob_xegony-WAR-Inventory.txt")
    assert char == "Bob"
    assert server == "xegony"
    assert cls == "WAR"


def test_extract_stablub_slot2():
    path = EXAMPLES / "Stablub_bristle-Inventory.txt"
    data = parse_inventory_file(path)
    assert data is not None
    assert data.character == "Stablub"
    slot2 = {s.gear_slot: s for s in extract_slot2_augs(data)}
    assert "Charm" in slot2
    assert slot2["Charm"].name == "Arcane Gem of Artfulness"
    assert "Range" in slot2
    # Short Bow → type 7/8 is Range-Slot4 (not Slot2 weapon aug)
    assert slot2["Range"].name == "Protector's Gem of Uprising"
    assert slot2["Range"].dump_slot == 4
    assert slot2["Range"].parent_name == "Short Bow of Rebellion"
    assert "Ear-1" in slot2
    assert "Ear-2" in slot2
    assert slot2["Ear-1"].name == "Nimble Gem of Unraveling Order"
    assert slot2["Ear-2"].name == "Arcane Gem of Artfulness"
    assert "Wrist-1" in slot2 and "Wrist-2" in slot2
    # Bag Slot2 must not appear
    assert not any(s.gear_slot.startswith("General") for s in slot2.values())


def test_extract_fulub_empty_charm_slot2():
    path = EXAMPLES / "Fulub_xegony-Inventory.txt"
    data = parse_inventory_file(path)
    assert data is not None
    slot2 = {s.gear_slot: s for s in extract_slot2_augs(data)}
    assert "Charm" in slot2
    assert slot2["Charm"].name is None
    assert slot2["Charm"].item_id is None
    # Non-bow Range keeps Slot2
    assert slot2["Range"].name == "Blazing Icon of Solusek Ro"
    assert slot2["Range"].dump_slot == 2


def test_range_bow_detected_by_slots_and_name():
    from eq_augs.parser import (
        is_range_bow,
        range_has_bow_slots,
        range_name_looks_like_bow,
        type78_dump_slot_for_parent,
        type78_dump_slot_for_range,
    )

    assert range_has_bow_slots({1, 2, 3, 4})
    assert range_has_bow_slots({1, 2, 3, 4, 5})
    assert not range_has_bow_slots({1, 2, 3})
    assert range_name_looks_like_bow("Short Bow of Rebellion")
    assert range_name_looks_like_bow("Longbow of the Forest")
    assert range_name_looks_like_bow("Ornate Crossbow")
    assert not range_name_looks_like_bow("Favor of the Chosen")
    # Both signals required
    assert is_range_bow(slot_numbers={1, 2, 3, 4}, item_name="Short Bow of Rebellion")
    assert not is_range_bow(slot_numbers={1, 2, 3}, item_name="Short Bow of Rebellion")
    assert not is_range_bow(slot_numbers={1, 2, 3, 4}, item_name="Favor of the Chosen")
    assert type78_dump_slot_for_range(is_bow=True) == 4
    assert type78_dump_slot_for_range(is_bow=False) == 2
    assert type78_dump_slot_for_parent("Range", range_is_bow=True) == 4
    assert type78_dump_slot_for_parent("Range", range_is_bow=False) == 2


def test_discover_inventory_files():
    files = discover_inventory_files(EXAMPLES)
    names = {p.name for p in files}
    assert "Stablub_bristle-Inventory.txt" in names
    assert len(files) >= 3


def test_parent_name_is_shield():
    assert parent_name_is_shield("Tower Shield of Rebellion")
    assert parent_name_is_shield("Harbinger Scale Shield")
    assert parent_name_is_shield("Aegis of the Sea")
    assert parent_name_is_shield("Shimmering Aegis")
    assert not parent_name_is_shield("Short Spear of Resonant Fracture")
    assert not parent_name_is_shield("Empty")
    assert not parent_name_is_shield(None)
    assert not parent_name_is_shield("Windshield Wiper")  # no word-boundary Shield


def test_collect_owned_item_ids_includes_bags_excludes_empty():
    from eq_augs.parser import InventoryData, InventoryItem

    data = InventoryData(
        character="Test",
        server="xegony",
        filepath="Test_xegony-Inventory.txt",
        items=[
            InventoryItem("Ear", "Earring", 100, 1, 6),
            InventoryItem("Ear-Slot2", "Equipped Aug", 200, 1, 0),
            InventoryItem("General 1-Slot3", "Bag Aug", 300, 1, 0),
            InventoryItem("Bank 1-Slot1", "Bank Aug", 400, 1, 0),
            InventoryItem("Charm-Slot2", "Empty", 0, 0, 0),
            InventoryItem("General 2-Slot1", "Empty", 0, 0, 0),
        ],
    )
    owned = collect_owned_item_ids(data)
    assert owned == {100, 200, 300, 400}


def test_collect_owned_from_example_dump():
    path = EXAMPLES / "Fulub_xegony-Inventory.txt"
    data = parse_inventory_file(path)
    assert data is not None
    owned = collect_owned_item_ids(data)
    assert 175174 in owned  # Arcane Gem of Artfulness (equipped)
    assert 0 not in owned
    assert 13006 in owned  # Water Flask in bag
