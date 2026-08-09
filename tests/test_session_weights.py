"""Tests for session/advanced weight overrides."""

from __future__ import annotations

from eq_augs.weights import (
    clear_weights_cache,
    default_class_weights,
    resolve_weights,
    sanitize_weight_map,
    session_absolute_weights,
)


def setup_function() -> None:
    clear_weights_cache()


def test_default_class_weights_war():
    info = default_class_weights("WAR")
    assert info["classAbbr"] == "WAR"
    assert info["profile"] == "dex"
    assert "Dex" in info["profileLabel"]
    assert info["role"] == "tank"
    assert info["weights"]["ac"] >= 10.0
    assert "ac" in info["labels"]
    # Replacement combat categories always present; retired ones absent.
    for key in ("atk", "heal_amount", "spell_damage", "clairvoyance"):
        assert key in info["weights"]
    for key in ("accuracy", "combat_effects", "shielding", "stun_resist"):
        assert key not in info["weights"]


def test_sanitize_weight_map():
    cleaned = sanitize_weight_map({"ac": 12, "hdex": "3.5", "nope": 9, "hp": 0})
    assert cleaned == {"ac": 12.0, "hdex": 3.5}


def test_session_absolute_weights_replace_base():
    base = resolve_weights("WAR", "Head")
    custom = {"ac": 99.0, "hdex": 1.0}
    with session_absolute_weights(custom):
        w = resolve_weights("WAR", "Head")
    assert w["ac"] == 99.0
    assert w["hdex"] == 1.0
    assert "hp" not in w or abs(w.get("hp", 0)) < 1e-9
    # Outside session, defaults restored.
    assert resolve_weights("WAR", "Head") == base


def test_session_weights_still_apply_feet_ac_only():
    with session_absolute_weights({"ac": 20.0, "hdex": 50.0, "hp": 40.0}):
        feet = resolve_weights("WAR", "Feet")
    assert set(feet) == {"ac"}
    assert feet["ac"] > 20.0  # overlay boost then AC-only
