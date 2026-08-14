"""Tests for multi-server roster discovery and ordering."""

from __future__ import annotations

from pathlib import Path

from eq_augs.roster import (
    build_roster,
    discover_folder_character_choices,
    enrich_folder_choice_classes,
    export_prefix_from_roster,
    filter_inventories_for_bindings,
    format_character_display_name,
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


_INV = "Location\tName\tID\tCount\tSlots\nHead\tHelm\t1\t1\t0\n"
_CHEST_INV = (
    "Location\tName\tID\tCount\tSlots\n"
    "Chest\tRogue Chest\t175863\t1\t6\n"
)


def test_format_character_display_name():
    assert format_character_display_name("Deflub") == "Deflub"
    assert format_character_display_name("Deflub", "PAL") == "Deflub ( PAL )"
    assert format_character_display_name("Deflub", ("PAL", "SHD", "WAR")) == (
        "Deflub ( PAL, SHD, WAR )"
    )


def test_discover_keeps_class_tagged_inventories(tmp_path: Path):
    (tmp_path / "Deflub_bristle-Inventory.txt").write_text(_INV, encoding="utf-8")
    (tmp_path / "Deflub_bristle-PAL-Inventory.txt").write_text(_INV, encoding="utf-8")
    (tmp_path / "Deflub_bristle-SHD-Inventory.txt").write_text(_INV, encoding="utf-8")
    (tmp_path / "Deflub_bristle-WAR-Inventory.txt").write_text(_INV, encoding="utf-8")
    (tmp_path / "Stablub_bristle-Inventory.txt").write_text(_INV, encoding="utf-8")

    choices = discover_folder_character_choices(tmp_path)
    by_name = {c.character: c for c in choices}
    assert set(by_name) == {"Deflub", "Stablub"}

    deflub = by_name["Deflub"]
    names = {Path(p).name for p in deflub.paths}
    assert names == {
        "Deflub_bristle-PAL-Inventory.txt",
        "Deflub_bristle-SHD-Inventory.txt",
        "Deflub_bristle-WAR-Inventory.txt",
    }
    assert set(deflub.class_abbrs) == {"PAL", "SHD", "WAR"}
    assert deflub.summary == "3 inventory"
    assert "PAL" in deflub.display_name
    assert "WAR" in deflub.display_name
    assert "SHD" in deflub.display_name

    stablub = by_name["Stablub"]
    assert stablub.class_abbrs == ()
    assert Path(stablub.path).name == "Stablub_bristle-Inventory.txt"
    assert stablub.summary == "1 inventory"


def test_filter_inventories_drops_generic_when_class_tagged(tmp_path: Path):
    generic = tmp_path / "Deflub_bristle-Inventory.txt"
    pal = tmp_path / "Deflub_bristle-PAL-Inventory.txt"
    war = tmp_path / "Deflub_bristle-WAR-Inventory.txt"
    generic.write_text(_INV, encoding="utf-8")
    pal.write_text(_INV, encoding="utf-8")
    war.write_text(_INV, encoding="utf-8")
    kept = {p.name for p in filter_inventories_for_bindings([generic, pal, war])}
    assert kept == {
        "Deflub_bristle-PAL-Inventory.txt",
        "Deflub_bristle-WAR-Inventory.txt",
    }


def test_build_roster_expands_class_tagged_dumps(tmp_path: Path):
    generic = tmp_path / "Deflub_bristle-Inventory.txt"
    pal = tmp_path / "Deflub_bristle-PAL-Inventory.txt"
    war = tmp_path / "Deflub_bristle-WAR-Inventory.txt"
    generic.write_text(_INV, encoding="utf-8")
    pal.write_text(_INV, encoding="utf-8")
    war.write_text(_INV, encoding="utf-8")
    roster = build_roster([generic, pal, war])
    assert {(e.class_abbr, Path(e.path).name) for e in roster} == {
        ("PAL", "Deflub_bristle-PAL-Inventory.txt"),
        ("WAR", "Deflub_bristle-WAR-Inventory.txt"),
    }
    keys = {e.persona_key for e in roster}
    assert keys == {"Deflub_bristle_PAL", "Deflub_bristle_WAR"}


def test_enrich_folder_choice_classes_from_chest(tmp_path: Path):
    dump = tmp_path / "Stablub_bristle-Inventory.txt"
    dump.write_text(_CHEST_INV, encoding="utf-8")
    choices = discover_folder_character_choices(tmp_path)
    assert choices[0].class_abbrs == ()
    rl = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "raidloot_chest_175863_rog.html"
    ).read_text(encoding="utf-8")
    enriched = enrich_folder_choice_classes(
        choices,
        overrides={175863: (rl, None)},
        allow_network=False,
    )
    assert enriched[0].class_abbrs == ("ROG",)
    assert enriched[0].class_abbr == "ROG"
    assert enriched[0].display_name == "Stablub ( ROG )"
