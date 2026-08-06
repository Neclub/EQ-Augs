"""Tests for multi-server roster discovery and ordering."""

from __future__ import annotations

from pathlib import Path

from eq_augs.roster import (
    build_roster,
    discover_folder_character_choices,
    export_prefix_from_roster,
    order_by_persona_keys,
    persona_key,
    unique_servers,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "Example" / "Inventory Dumps"


def test_persona_key():
    assert persona_key("Stablub", "bristle") == "Stablub_bristle"
    assert persona_key("Bob", "xegony", "WAR") == "Bob_xegony_WAR"


def test_discover_folder_multi_server():
    choices = discover_folder_character_choices(EXAMPLES)
    assert len(choices) >= 3
    servers = unique_servers(choices)
    assert "bristle" in servers
    assert "xegony" in servers
    names = {(c.character, c.server) for c in choices}
    assert ("Stablub", "bristle") in names
    assert ("Fulub", "xegony") in names


def test_build_roster_respects_saved_order():
    choices = discover_folder_character_choices(EXAMPLES)
    paths = [c.path for c in choices]
    order = [
        persona_key("Tanklub", "xegony"),
        persona_key("Stablub", "bristle"),
    ]
    roster = build_roster(paths, saved_order=order)
    assert roster[0].character == "Tanklub"
    assert roster[1].character == "Stablub"
    # Remaining characters follow after saved order
    assert len(roster) >= 3


def test_export_prefix_multi_server():
    choices = discover_folder_character_choices(EXAMPLES)
    roster = build_roster([c.path for c in choices])
    assert export_prefix_from_roster(roster) == "Team"
    one = build_roster([choices[0].path])
    assert export_prefix_from_roster(one) == one[0].character


def test_order_by_persona_keys():
    items = [{"k": "b"}, {"k": "a"}, {"k": "c"}]
    ordered = order_by_persona_keys(items, ["c", "a"], key_fn=lambda x: x["k"])
    assert [x["k"] for x in ordered] == ["c", "a", "b"]
