"""Tests for role/class/slot weight resolution and scoring."""

from __future__ import annotations

from eq_augs.raidloot import AugCandidate
from eq_augs.weights import (
    clear_weights_cache,
    rank_key,
    resolve_weights,
    score_aug,
    uses_feet_overlay,
)


def setup_function() -> None:
    clear_weights_cache()


def _aug(**kwargs) -> AugCandidate:
    base = dict(
        item_id=1,
        name="Test Aug",
        profile="dex",
        focus_heroic=50,
        ac=100,
        hp=1000,
        atk=40,
        stats={"ac": 100, "hp": 1000, "atk": 40, "hdex": 50},
    )
    base.update(kwargs)
    return AugCandidate(**base)


def test_role_class_merge_warrior():
    w = resolve_weights("WAR", "Head")
    assert w == {"ac": 10.0, "hdex": 8.0}
    assert "accuracy" not in w
    assert "combat_effects" not in w
    assert "shielding" not in w
    assert "stun_resist" not in w


def test_simplified_role_focus_stats():
    assert resolve_weights("ROG", "Head") == {"hdex": 10.0}
    assert resolve_weights("RNG", "Head") == {"hdex": 10.0}
    assert resolve_weights("CLR", "Head") == {"hwis": 10.0}
    assert resolve_weights("WIZ", "Head") == {
        "spell_damage": 10.0,
        "hint": 1.0,
        "hwis": 1.0,
        "hdex": 1.0,
    }


def test_feet_overlay_war_not_rog():
    war_head = resolve_weights("WAR", "Head")
    war_feet = resolve_weights("WAR", "Feet")
    assert war_feet["ac"] > war_head["ac"]
    assert uses_feet_overlay("WAR")
    assert not uses_feet_overlay("ROG")
    rog_feet = resolve_weights("ROG", "Feet")
    rog_head = resolve_weights("ROG", "Head")
    assert rog_feet.get("ac", 0) == rog_head.get("ac", 0)
    assert rog_feet == rog_head


def test_feet_ac_dominates_other_weights():
    """Feet high-AC classes: scoring weights are AC-only."""
    for cls in ("WAR", "MNK", "RNG", "BST", "BRD"):
        w = resolve_weights(cls, "Feet")
        assert set(w) == {"ac"}, cls
        assert w["ac"] >= 50.0, cls


def test_score_missing_stats_zero():
    aug = _aug(
        focus_heroic=60,
        ac=0,
        hp=0,
        atk=0,
        stats={"hdex": 60},
    )
    w = {"hdex": 10.0, "ac": 5.0}
    assert score_aug(aug, w) == 600.0


def test_feet_prefers_high_ac_for_war():
    high_dex = _aug(
        item_id=1,
        name="Dex Gem",
        focus_heroic=70,
        ac=80,
        hp=1200,
        atk=70,
        stats={"hdex": 70, "ac": 80, "hp": 1200, "atk": 70},
    )
    high_ac = _aug(
        item_id=2,
        name="AC Gem",
        focus_heroic=30,
        ac=140,
        hp=1200,
        atk=30,
        stats={"hdex": 30, "ac": 140, "hp": 1200, "atk": 30},
    )
    # ROG Head favors HDex; WAR Feet overlay flips toward AC.
    head_order = sorted(
        [high_dex, high_ac], key=lambda a: rank_key(a, "ROG", "Head")
    )
    feet_order = sorted(
        [high_dex, high_ac], key=lambda a: rank_key(a, "WAR", "Feet")
    )
    assert head_order[0].item_id == 1
    assert feet_order[0].item_id == 2


def test_feet_small_ac_edge_beats_focus_for_war():
    """A few AC points must outweigh much higher focus/ATK on Feet for WAR."""
    more_focus = _aug(
        item_id=1,
        name="Focus Gem",
        focus_heroic=70,
        ac=113,
        hp=1200,
        atk=80,
        stats={"hdex": 70, "ac": 113, "hp": 1200, "atk": 80},
    )
    more_ac = _aug(
        item_id=2,
        name="AC Gem",
        focus_heroic=20,
        ac=116,
        hp=900,
        atk=20,
        stats={"hdex": 20, "ac": 116, "hp": 900, "atk": 20},
    )
    order = sorted(
        [more_focus, more_ac], key=lambda a: rank_key(a, "WAR", "Feet")
    )
    assert order[0].item_id == 2


def test_wiz_prefers_spell_damage_over_hint():
    more_hint = _aug(
        item_id=1,
        name="HInt Gem",
        profile="int",
        focus_heroic=60,
        stats={"hint": 60, "spell_damage": 80, "ac": 100, "hp": 1000},
    )
    more_sd = _aug(
        item_id=2,
        name="Nuke Gem",
        profile="int",
        focus_heroic=40,
        stats={"hint": 40, "spell_damage": 120, "ac": 100, "hp": 1000},
    )
    order = sorted(
        [more_hint, more_sd], key=lambda a: rank_key(a, "WIZ", "Head")
    )
    assert order[0].item_id == 2


def test_wiz_prefers_high_spell_damage_dex_aug():
    """Spell Damage dominates; a Dex aug with more SD beats a higher-HInt INT aug."""
    int_aug = _aug(
        item_id=1,
        name="HInt Gem",
        profile="int",
        focus_heroic=61,
        stats={"hint": 61, "spell_damage": 100, "ac": 100, "hp": 1500},
    )
    dex_aug = _aug(
        item_id=2,
        name="Dex SD Gem",
        profile="dex",
        focus_heroic=61,
        stats={"hdex": 61, "spell_damage": 114, "ac": 115, "hp": 1750},
    )
    order = sorted(
        [int_aug, dex_aug], key=lambda a: rank_key(a, "WIZ", "Head")
    )
    assert order[0].item_id == 2


def test_wiz_falls_back_to_hint_when_spell_damage_missing():
    more_hint = _aug(
        item_id=1,
        name="HInt Gem",
        profile="int",
        focus_heroic=60,
        stats={"hint": 60, "ac": 100, "hp": 1000},
    )
    less_hint = _aug(
        item_id=2,
        name="Low HInt Gem",
        profile="int",
        focus_heroic=40,
        stats={"hint": 40, "ac": 100, "hp": 1000},
    )
    order = sorted(
        [more_hint, less_hint], key=lambda a: rank_key(a, "WIZ", "Head")
    )
    assert order[0].item_id == 1


def test_shield_overlay_requires_flag():
    plain = resolve_weights("PAL", "Secondary", secondary_is_shield=False)
    shield = resolve_weights("PAL", "Secondary", secondary_is_shield=True)
    assert shield["ac"] > plain.get("ac", 0)
