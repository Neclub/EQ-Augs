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


def test_serialize_default_focus_filter_prefers_hdex():
    from eq_augs.export_bundle import ExportBundle
    from eq_augs.html_export import serialize_report
    from eq_augs.raidloot import CatalogResult

    dex = _aug(item_id=1, name="Dex Aug", profile="dex", focus_heroic=60)
    intel = _aug(item_id=2, name="Int Aug", profile="int", focus_heroic=55)
    catalog = CatalogResult(
        profile="dex",
        augs=[dex],
        fetched_at="t",
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
    assert {p["label"] for p in payload["rankedProfiles"]} == {"HDex", "HInt"}
    assert payload["rankedAugs"][0]["focusLabel"] == "HDex"
    assert payload["rankedAugs"][1]["focusLabel"] == "HInt"


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
    )
    payload = serialize_report(bundle)
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
        }
    ]
    upgrade = payload["upgrades"][0]
    assert upgrade["recommendedOwned"] is False
    assert upgrade["recommendedExpansion"] == "Shattering of Ro"


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
