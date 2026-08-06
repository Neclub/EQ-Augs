"""Tests for parent-item type 7/8 socket map lookup."""

from __future__ import annotations

from pathlib import Path

from eq_augs.item_sockets import (
    fetch_item_sockets,
    parse_eqresource_item_html,
    parse_raidloot_item_html,
    resolve_type78_slots,
    type78_dump_slot,
)
from eq_augs.parser import (
    InventoryData,
    InventoryItem,
    collect_equipped_parent_ids,
    extract_slot2_augs,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_parse_raidloot_head_slot2_type8():
    html = (FIXTURES / "raidloot_item_175860.html").read_text(encoding="utf-8")
    sockets = parse_raidloot_item_html(html, 175860)
    assert type78_dump_slot(sockets) == 2
    assert [(s.slot, s.aug_type) for s in sockets] == [(1, 5), (2, 8), (3, 14)]


def test_parse_raidloot_ear_slot3_type8():
    html = (FIXTURES / "raidloot_item_175914.html").read_text(encoding="utf-8")
    sockets = parse_raidloot_item_html(html, 175914)
    assert type78_dump_slot(sockets) == 3


def test_parse_raidloot_face_evolver_slot4():
    html = (FIXTURES / "raidloot_item_168096.html").read_text(encoding="utf-8")
    sockets = parse_raidloot_item_html(html, 168096)
    assert type78_dump_slot(sockets) == 4


def test_parse_eqresource_fallback_face():
    html = (FIXTURES / "eqresource_item_168096.html").read_text(encoding="utf-8")
    sockets = parse_eqresource_item_html(html)
    assert type78_dump_slot(sockets) == 4
    assert any(s.slot == 6 and s.aug_type == 19 for s in sockets)


def test_type78_picks_first_of_7_and_8():
    html = (
        '<label>Slot 1, type 3:</label>'
        '<label>Slot 2, type 7:</label>'
        '<label>Slot 3, type 8:</label>'
    )
    sockets = parse_raidloot_item_html(html)
    assert type78_dump_slot(sockets) == 2


def test_fetch_override_raidloot_then_eqr():
    raid = (FIXTURES / "raidloot_item_168096.html").read_text(encoding="utf-8")
    sock = fetch_item_sockets(168096, html_override=raid)
    assert type78_dump_slot(sock.sockets) == 4
    assert sock.source == "raidloot"

    eqr = (FIXTURES / "eqresource_item_168096.html").read_text(encoding="utf-8")
    sock2 = fetch_item_sockets(168096, html_override="<html></html>", eqr_html_override=eqr)
    assert type78_dump_slot(sock2.sockets) == 4
    assert sock2.source == "eqresource"


def test_resolve_type78_slots_with_overrides():
    overrides = {
        175860: ((FIXTURES / "raidloot_item_175860.html").read_text(encoding="utf-8"), None),
        175914: ((FIXTURES / "raidloot_item_175914.html").read_text(encoding="utf-8"), None),
        168096: ((FIXTURES / "raidloot_item_168096.html").read_text(encoding="utf-8"), None),
    }
    resolved = resolve_type78_slots([175860, 175914, 168096], overrides=overrides)
    assert resolved[175860] == 2
    assert resolved[175914] == 3
    assert resolved[168096] == 4


def test_extract_face_evolver_uses_slot4_map():
    data = InventoryData(
        character="Shieldlub",
        server="test",
        filepath="x",
        items=[
            InventoryItem("Face", "Yearning Restored Mask of the Vortex", 168096, 1, 6),
            InventoryItem("Face-Slot2", "Empty", 0, 0, 0),
            InventoryItem("Face-Slot3", "Empty", 0, 0, 0),
            InventoryItem("Face-Slot4", "Protector's Gem of Uprising", 173574, 1, 6),
        ],
    )
    without = {s.gear_slot: s for s in extract_slot2_augs(data)}
    assert without["Face"].name is None  # heuristic Slot2 empty
    assert without["Face"].dump_slot == 2

    with_map = {
        s.gear_slot: s
        for s in extract_slot2_augs(data, type78_slot_by_parent_id={168096: 4})
    }
    assert with_map["Face"].name == "Protector's Gem of Uprising"
    assert with_map["Face"].dump_slot == 4
    assert with_map["Face"].parent_id == 168096
    assert with_map["Face"].socket_map_hit is True


def test_collect_parent_ids_skips_primary_and_weapon_secondary():
    data = InventoryData(
        character="X",
        server="s",
        filepath="x",
        items=[
            InventoryItem("Head", "Helm", 100, 1, 6),
            InventoryItem("Primary", "Sword", 200, 1, 6),
            InventoryItem("Secondary", "Spear", 300, 1, 6),
        ],
    )
    ids = collect_equipped_parent_ids(data)
    assert ids == [100]

    shield = InventoryData(
        character="X",
        server="s",
        filepath="x",
        items=[
            InventoryItem("Secondary", "Tower Shield of Rebellion", 173941, 1, 6),
        ],
    )
    assert collect_equipped_parent_ids(shield) == [173941]