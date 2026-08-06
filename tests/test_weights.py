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
    assert w["ac"] >= 10.0  # tank 10 + war +1
    assert w["hdex"] >= 8.0
    assert "heal_amount" not in w or w.get("heal_amount", 0) == 0


def test_feet_overlay_war_not_rog():
    war_head = resolve_weights("WAR", "Head")
    war_feet = resolve_weights("WAR", "Feet")
    assert war_feet["ac"] > war_head["ac"]
    assert uses_feet_overlay("WAR")
    assert not uses_feet_overlay("ROG")
    rog_feet = resolve_weights("ROG", "Feet")
    rog_head = resolve_weights("ROG", "Head")
    assert rog_feet["ac"] == rog_head["ac"]


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


def test_shield_overlay_requires_flag():
    plain = resolve_weights("PAL", "Secondary", secondary_is_shield=False)
    shield = resolve_weights("PAL", "Secondary", secondary_is_shield=True)
    assert shield["ac"] > plain.get("ac", 0)
