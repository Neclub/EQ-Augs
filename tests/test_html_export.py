"""Tests for HTML report serialization helpers."""

from __future__ import annotations

from eq_augs.html_export import ranked_aug_type
from eq_augs.raidloot import AugCandidate


def _aug(**kwargs) -> AugCandidate:
    base = dict(
        item_id=1,
        name="Test",
        profile="dex",
        focus_heroic=50,
    )
    base.update(kwargs)
    return AugCandidate(**base)


def test_ranked_aug_type_buckets():
    assert ranked_aug_type(_aug(ear_only=True, allowed_bases=frozenset({"Ear"}))) == "Ear"
    assert ranked_aug_type(_aug(shield_only=True, allowed_bases=frozenset({"Secondary"}))) == "Shield"
    assert (
        ranked_aug_type(
            _aug(excluded_bases=frozenset({"Charm", "Range", "Primary", "Secondary", "Ammo"}))
        )
        == "General"
    )
    assert (
        ranked_aug_type(_aug(excluded_bases=frozenset({"Range", "Primary", "Secondary", "Ammo"})))
        == "Charm"
    )
    assert (
        ranked_aug_type(_aug(excluded_bases=frozenset({"Primary", "Secondary", "Ammo"})))
        == "Charm/Range"
    )


def test_format_catalog_fetched_at_shortens_iso():
    from eq_augs.html_export import format_catalog_fetched_at

    assert (
        format_catalog_fetched_at("2026-08-12T18:59:52.520177+00:00")
        == "2026-08-12 18:59 UTC"
    )
    assert format_catalog_fetched_at("t") == "t"
    assert format_catalog_fetched_at("") == ""


def test_serialize_default_focus_filter_prefers_hdex():
    from eq_augs import __version__
    from eq_augs.export_bundle import ExportBundle
    from eq_augs.html_export import serialize_report
    from eq_augs.raidloot import CatalogResult

    dex = _aug(item_id=1, name="Dex Aug", profile="dex", focus_heroic=60)
    intel = _aug(item_id=2, name="Int Aug", profile="int", focus_heroic=55)
    catalog = CatalogResult(
        profile="dex",
        augs=[dex],
        fetched_at="2026-08-12T18:59:52.520177+00:00",
        from_cache=False,
        url="http://test",
    )
    bundle = ExportBundle(
        profile="dex",
        profile_label="Dex (melee)",
        artisans_prize_owned=False,
        catalog=catalog,
        characters=[],
        ranked_augs=[dex, intel],
    )
    payload = serialize_report(bundle)
    assert payload["defaultFocusFilter"] == "HDex"
    assert payload["reportTitle"] == "Team Type 7/8 Augs"
    assert {p["label"] for p in payload["rankedProfiles"]} == {"HDex", "HInt"}
    assert payload["rankedAugs"][0]["focusLabel"] == "HDex"
    assert payload["rankedAugs"][1]["focusLabel"] == "HInt"
    assert payload["appVersion"] == __version__
    assert payload["catalogFetchedAt"] == "2026-08-12 18:59 UTC"
    assert payload["logoDataUri"].startswith("data:image/png;base64,")


def test_serialize_farm_list_and_eqresource_links():
    from eq_augs.compare import CharacterSlot2Report, FarmListEntry, Slot2Comparison
    from eq_augs.export_bundle import ExportBundle
    from eq_augs.html_export import EQRESOURCE_ITEM_URL, serialize_report
    from eq_augs.raidloot import CatalogResult

    catalog = CatalogResult(
        profile="dex",
        augs=[],
        fetched_at="t",
        from_cache=False,
        url="http://test",
    )
    cmp_ = Slot2Comparison(
        gear_slot="Arms",
        current_name="Old Aug",
        current_id=1,
        recommended_name="Joy of the Dancer",
        recommended_id=175169,
        recommended_focus=41,
        status="upgrade",
        note="test",
        recommended_owned=False,
        recommended_expansion="Shattering of Ro",
    )
    ch = CharacterSlot2Report(
        character="Farmer",
        server="xegony",
        class_abbr="ROG",
        profile="dex",
        filepath="Farmer_xegony-Inventory.txt",
        comparisons=[cmp_],
        owned_item_ids={1},
        slots_changed=1,
        stat_summary={
            "focus": 12,
            "ac": 20,
            "hp": 333,
            "atk": 5,
            "heal_amount": 0,
            "spell_damage": 0,
            "clairvoyance": 0,
        },
    )
    farm = FarmListEntry(
        character="Farmer",
        server="xegony",
        persona_key="Farmer|xegony|ROG",
        gear_slot="Arms",
        name="Joy of the Dancer",
        item_id=175169,
        expansion="Shattering of Ro",
    )
    bundle = ExportBundle(
        profile="dex",
        profile_label="Dex (melee)",
        artisans_prize_owned=False,
        catalog=catalog,
        characters=[ch],
        farm_list=[farm],
        ranked_augs=[_aug(item_id=175169, name="Joy of the Dancer")],
        export_prefix="Farmer",
    )
    payload = serialize_report(bundle)
    assert payload["reportTitle"] == "Farmer - ROG Type 7/8 Augs"
    assert payload["eqResourceItemUrl"] == EQRESOURCE_ITEM_URL
    assert "eqresource.com" in payload["eqResourceItemUrl"]
    assert payload["farmList"] == [
        {
            "personaKey": "Farmer|xegony|ROG",
            "character": "Farmer",
            "gearSlot": "Arms",
            "name": "Joy of the Dancer",
            "itemId": 175169,
            "expansion": "Shattering of Ro",
            "craftComponentName": None,
            "craftComponentId": None,
            "craftComponentOwned": None,
        }
    ]
    upgrade = payload["upgrades"][0]
    assert upgrade["recommendedOwned"] is False
    assert upgrade["recommendedExpansion"] == "Shattering of Ro"
    assert payload["statSummary"] == [
        {
            "personaKey": "Farmer_xegony_ROG",
            "character": "Farmer",
            "columnLabel": "Farmer",
            "focusLabel": "HDex",
            "slotsChanged": 1,
            "focus": 12,
            "ac": 20,
            "hp": 333,
            "atk": 5,
            "healAmount": 0,
            "spellDamage": 0,
            "clairvoyance": 0,
        }
    ]
    assert payload["characters"][0]["profile"] == "dex"
    assert payload["characters"][0]["profileLabel"] == "Dex (melee)"


def test_serialize_per_character_profile_labels():
    from eq_augs.compare import CharacterSlot2Report
    from eq_augs.export_bundle import ExportBundle
    from eq_augs.html_export import serialize_report
    from eq_augs.raidloot import CatalogResult

    catalog = CatalogResult(
        profile="dex",
        augs=[],
        fetched_at="t",
        from_cache=False,
        url="http://test",
    )
    chars = [
        CharacterSlot2Report(
            character="Tank",
            server="bristle",
            class_abbr="WAR",
            profile="dex",
            filepath="Tank_bristle-WAR-Inventory.txt",
            comparisons=[],
        ),
        CharacterSlot2Report(
            character="Priest",
            server="bristle",
            class_abbr="CLR",
            profile="wis",
            filepath="Priest_bristle-CLR-Inventory.txt",
            comparisons=[],
        ),
        CharacterSlot2Report(
            character="Caster",
            server="xegony",
            class_abbr="WIZ",
            profile="int",
            filepath="Caster_xegony-WIZ-Inventory.txt",
            comparisons=[],
        ),
    ]
    payload = serialize_report(
        ExportBundle(
            profile="dex",
            profile_label="Dex (melee)",
            artisans_prize_owned=False,
            catalog=catalog,
            characters=chars,
            ranked_augs=[],
        )
    )
    by_name = {c["character"]: c for c in payload["characters"]}
    assert by_name["Tank"]["profileLabel"] == "Dex (melee)"
    assert by_name["Priest"]["profileLabel"] == "WIS (priests)"
    assert by_name["Caster"]["profileLabel"] == "INT (casters)"
    assert by_name["Caster"]["server"] == "xegony"
    assert payload["reportTitle"] == "Team Type 7/8 Augs"


def test_serialize_single_character_title_includes_class():
    from eq_augs.compare import CharacterSlot2Report
    from eq_augs.export_bundle import ExportBundle
    from eq_augs.html_export import serialize_report
    from eq_augs.raidloot import CatalogResult

    catalog = CatalogResult(
        profile="dex",
        augs=[],
        fetched_at="t",
        from_cache=False,
        url="http://test",
    )
    payload = serialize_report(
        ExportBundle(
            profile="dex",
            profile_label="Dex (melee)",
            artisans_prize_owned=False,
            catalog=catalog,
            characters=[
                CharacterSlot2Report(
                    character="Deflub",
                    server="bristle",
                    class_abbr="WAR",
                    profile="dex",
                    filepath="Deflub_bristle-WAR-Inventory.txt",
                    comparisons=[],
                )
            ],
            ranked_augs=[],
            export_prefix="Deflub",
        )
    )
    assert payload["reportTitle"] == "Deflub - WAR Type 7/8 Augs"


def test_build_farm_list_skips_owned_recommendations():
    from eq_augs.compare import CharacterSlot2Report, Slot2Comparison
    from eq_augs.export_bundle import build_farm_list

    owned_cmp = Slot2Comparison(
        gear_slot="Head",
        current_name="Old",
        current_id=1,
        recommended_name="Have It",
        recommended_id=10,
        recommended_focus=50,
        status="upgrade",
        recommended_owned=True,
        recommended_expansion="Shattering of Ro",
    )
    farm_cmp = Slot2Comparison(
        gear_slot="Arms",
        current_name="Old",
        current_id=2,
        recommended_name="Need It",
        recommended_id=20,
        recommended_focus=50,
        status="upgrade",
        recommended_owned=False,
        recommended_expansion="Night of Shadows",
    )
    bis_cmp = Slot2Comparison(
        gear_slot="Feet",
        current_name="BiS",
        current_id=30,
        recommended_name="BiS",
        recommended_id=30,
        recommended_focus=50,
        status="bis",
        recommended_owned=True,
    )
    ch = CharacterSlot2Report(
        character="X",
        server="s",
        class_abbr=None,
        profile="dex",
        filepath="x",
        comparisons=[owned_cmp, farm_cmp, bis_cmp],
    )
    farm = build_farm_list([ch], [])
    assert len(farm) == 1
    assert farm[0].item_id == 20
    assert farm[0].expansion == "Night of Shadows"
    assert farm[0].craft_component_name is None
    assert farm[0].craft_component_owned is None


def test_build_farm_list_carries_craft_component_owned():
    from eq_augs.compare import CharacterSlot2Report, Slot2Comparison
    from eq_augs.export_bundle import build_farm_list

    farm_cmp = Slot2Comparison(
        gear_slot="Waist",
        current_name="Old",
        current_id=2,
        recommended_name="Acrobat's Gem of Unraveling Order",
        recommended_id=175572,
        recommended_focus=61,
        status="upgrade",
        recommended_owned=False,
        craft_component_name="Unraveling Focus of Fortitude",
        craft_component_id=170818,
        craft_component_owned=True,
    )
    ch = CharacterSlot2Report(
        character="X",
        server="s",
        class_abbr=None,
        profile="dex",
        filepath="x",
        comparisons=[farm_cmp],
    )
    farm = build_farm_list([ch], [])
    assert len(farm) == 1
    assert farm[0].craft_component_owned is True
    assert farm[0].craft_component_name == "Unraveling Focus of Fortitude"


def test_build_farm_list_one_per_lore_group():
    from eq_augs.compare import CharacterSlot2Report, Slot2Comparison
    from eq_augs.export_bundle import build_farm_list

    mystic = Slot2Comparison(
        gear_slot="Head",
        current_name=None,
        current_id=None,
        recommended_name="Mystic's Gem of Unraveling Order",
        recommended_id=175573,
        recommended_focus=61,
        status="empty",
        recommended_owned=False,
    )
    defender = Slot2Comparison(
        gear_slot="Arms",
        current_name=None,
        current_id=None,
        recommended_name="Defender's Gem of Unraveling Order",
        recommended_id=175571,
        recommended_focus=0,
        status="empty",
        recommended_owned=False,
    )
    ch = CharacterSlot2Report(
        character="X",
        server="s",
        class_abbr="WIZ",
        profile="int",
        filepath="x",
        comparisons=[mystic, defender],
    )
    farm = build_farm_list(
        [ch],
        [],
        lore_group_by_id={175573: "175571", 175571: "175571"},
    )
    assert [e.item_id for e in farm] == [175573]
