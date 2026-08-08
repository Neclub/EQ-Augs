"""Data-driven role → class → slot overlay weights for aug scoring."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from eq_augs.aug_stats import STAT_DISPLAY, STAT_KEYS
from eq_augs.package_data import data_dir
from eq_augs.profiles import CLASS_TO_PROFILE, FEET_HIGH_AC_CLASSES, ProfileId
from eq_augs.raidloot import AugCandidate
from eq_augs.slots import EAR_REPORT_SLOTS

OVERRIDE_FILENAME = "weight_overrides.json"


def _appdata_root() -> Path:
    local = os.environ.get("LOCALAPPDATA") or os.environ.get("HOME") or "."
    root = Path(local) / "EQ Augs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def override_path() -> Path:
    return _appdata_root() / OVERRIDE_FILENAME


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_packaged() -> tuple[dict, dict, dict]:
    base = data_dir() / "weights"
    roles = _read_json(base / "roles.json")
    classes = _read_json(base / "classes.json")
    overlays = _read_json(base / "slot_overlays.json")
    return roles, classes, overlays


def _merge_weight_maps(
    base: Mapping[str, float], *deltas: Mapping[str, float] | None
) -> dict[str, float]:
    out: dict[str, float] = {k: float(v) for k, v in base.items() if k in STAT_KEYS}
    for delta in deltas:
        if not delta:
            continue
        for k, v in delta.items():
            if k not in STAT_KEYS:
                continue
            out[k] = float(out.get(k, 0.0)) + float(v)
    # Drop zero / near-zero weights so missing stats stay free.
    return {k: v for k, v in out.items() if abs(v) > 1e-9}


def _gear_slot_base(gear_slot: str) -> str:
    if gear_slot in EAR_REPORT_SLOTS or gear_slot.startswith("Ear"):
        return "Ear"
    if gear_slot.startswith("Wrist"):
        return "Wrist"
    if gear_slot.startswith("Fingers"):
        return "Fingers"
    return gear_slot


def _default_role_for_profile(profile: ProfileId) -> str:
    if profile == "int":
        return "pure_caster"
    if profile == "wis":
        return "priest"
    return "melee_dps"


@lru_cache(maxsize=1)
def _tables() -> tuple[dict, dict, dict, dict]:
    roles_doc, classes_doc, overlays_doc = _load_packaged()
    override = _read_json(override_path())
    return roles_doc, classes_doc, overlays_doc, override


def clear_weights_cache() -> None:
    """Test helper — drop cached JSON tables."""
    _tables.cache_clear()


def class_role(class_abbr: str | None) -> str | None:
    if not class_abbr:
        return None
    roles_doc, classes_doc, _overlays_doc, override = _tables()
    key = class_abbr.strip().upper()
    ov_classes = (override.get("classes") or {}) if isinstance(override.get("classes"), dict) else {}
    entry = ov_classes.get(key) or (classes_doc.get("classes") or {}).get(key)
    if isinstance(entry, dict) and entry.get("role"):
        return str(entry["role"])
    # Fallback from catalog profile map
    profile = CLASS_TO_PROFILE.get(key)
    if profile:
        return _default_role_for_profile(profile)
    _ = roles_doc
    return None


def resolve_weights(
    class_abbr: str | None,
    gear_slot: str,
    *,
    secondary_is_shield: bool = False,
    profile: ProfileId | None = None,
) -> dict[str, float]:
    """
    Effective weights = role base ⊕ class modifiers ⊕ slot overlays ⊕ AppData overrides.
    """
    roles_doc, classes_doc, overlays_doc, override = _tables()
    roles = roles_doc.get("roles") or {}
    classes = classes_doc.get("classes") or {}

    key = (class_abbr or "").strip().upper() or None
    packaged = dict(classes.get(key) or {}) if key else {}
    ov_classes = override.get("classes") if isinstance(override.get("classes"), dict) else {}
    ov_entry = dict(ov_classes.get(key) or {}) if key else {}

    role_name = str(ov_entry.get("role") or packaged.get("role") or "")
    if not role_name:
        use_profile = profile or (CLASS_TO_PROFILE.get(key) if key else None) or "dex"
        role_name = _default_role_for_profile(use_profile)  # type: ignore[arg-type]

    role_base = dict(roles.get(role_name) or {})
    ov_roles = override.get("roles") if isinstance(override.get("roles"), dict) else {}
    if role_name in ov_roles and isinstance(ov_roles[role_name], dict):
        # Role key overrides replace individual weights (not additive).
        role_base = {**role_base, **{k: float(v) for k, v in ov_roles[role_name].items()}}

    class_mods = {
        **(packaged.get("modifiers") or {}),
        **(ov_entry.get("modifiers") or {}),
    }

    slot_base = _gear_slot_base(gear_slot)
    overlay_mods: dict[str, float] = {}
    feet_ac_priority = False
    for overlay in overlays_doc.get("overlays") or []:
        if not isinstance(overlay, dict):
            continue
        slots = overlay.get("slots") or []
        if slot_base not in slots and gear_slot not in slots:
            continue
        classes_filter = overlay.get("classes")
        if classes_filter is not None:
            allowed = {c.upper() for c in classes_filter}
            if not key or key not in allowed:
                continue
        if overlay.get("require_shield") and not secondary_is_shield:
            continue
        if overlay.get("id") == "feet_high_ac":
            feet_ac_priority = True
        for k, v in (overlay.get("modifiers") or {}).items():
            overlay_mods[k] = float(overlay_mods.get(k, 0.0)) + float(v)

    # Extra additive overrides: {"stat_overrides": {...}} or {"weights": {"WAR": {...}}}
    flat: dict[str, float] = {}
    if isinstance(override.get("stat_overrides"), dict):
        for k, v in override["stat_overrides"].items():
            flat[k] = float(v)
    if key and isinstance(override.get("weights"), dict):
        per = override["weights"].get(key)
        if isinstance(per, dict):
            for k, v in per.items():
                flat[k] = float(flat.get(k, 0.0)) + float(v)

    merged = _merge_weight_maps(role_base, class_mods, overlay_mods, flat)
    if feet_ac_priority:
        return _apply_feet_ac_dominance(merged)
    return merged


def _apply_feet_ac_dominance(weights: dict[str, float]) -> dict[str, float]:
    """
    For Feet on high-AC classes, ranking is AC-only.

    Other role/class weights are dropped so focus/HP/ATK cannot outweigh AC.
    Equal-AC ties still break via ``rank_key`` (HP, then AC, then name).
    """
    return {"ac": float(weights.get("ac", 0.0))}


def score_aug(aug: AugCandidate, weights: Mapping[str, float]) -> float:
    stats = aug.effective_stats() if hasattr(aug, "effective_stats") else dict(aug.stats or {})
    total = 0.0
    for key, weight in weights.items():
        total += float(stats.get(key, 0)) * float(weight)
    return total


def score_delta_contributors(
    current: AugCandidate | None,
    recommended: AugCandidate,
    weights: Mapping[str, float],
    *,
    top_n: int = 3,
) -> list[tuple[str, float]]:
    """Return top weighted delta contributors (display_label, weighted_delta)."""
    cur = current.effective_stats() if current is not None else {}
    rec = recommended.effective_stats()
    parts: list[tuple[str, float]] = []
    for key, weight in weights.items():
        d = (float(rec.get(key, 0)) - float(cur.get(key, 0))) * float(weight)
        if abs(d) < 1e-9:
            continue
        parts.append((STAT_DISPLAY.get(key, key), d))
    parts.sort(key=lambda x: (-abs(x[1]), x[0]))
    return parts[:top_n]


def rank_key(
    aug: AugCandidate,
    class_abbr: str | None,
    gear_slot: str,
    *,
    secondary_is_shield: bool = False,
    profile: ProfileId | None = None,
) -> tuple:
    """Sort key: higher score first, then HP, AC, name."""
    weights = resolve_weights(
        class_abbr,
        gear_slot,
        secondary_is_shield=secondary_is_shield,
        profile=profile or aug.profile,
    )
    score = score_aug(aug, weights)
    return (-score, -aug.hp, -aug.ac, aug.name.casefold())


def uses_feet_overlay(class_abbr: str | None) -> bool:
    """True when Feet high-AC overlay applies (same set as legacy FEET_HIGH_AC)."""
    if not class_abbr:
        return False
    key = class_abbr.strip().upper()
    # Prefer overlay JSON list when present.
    _roles_doc, _classes_doc, overlays_doc, _override = _tables()
    for overlay in overlays_doc.get("overlays") or []:
        if not isinstance(overlay, dict):
            continue
        if overlay.get("id") != "feet_high_ac":
            continue
        classes = overlay.get("classes") or []
        return key in {c.upper() for c in classes}
    return key in FEET_HIGH_AC_CLASSES
