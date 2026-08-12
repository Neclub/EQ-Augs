"""Dex / INT / WIS profiles and class → profile mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ProfileId = Literal["dex", "int", "wis"]

PROFILES: tuple[ProfileId, ...] = ("dex", "int", "wis")

PROFILE_LABELS: dict[ProfileId, str] = {
    "dex": "Dex (melee)",
    "int": "INT (casters)",
    "wis": "WIS (priests)",
}

# Focus heroic attribute used for ranking within each profile.
PROFILE_FOCUS_STAT: dict[ProfileId, str] = {
    "dex": "hdex",
    "int": "hint",
    "wis": "hwis",
}

# Display labels for notes / ranked columns (raidloot-style).
PROFILE_FOCUS_LABEL: dict[ProfileId, str] = {
    "dex": "HDex",
    "int": "HInt",
    "wis": "HWis",
}

# Shield-only type 7/8 augs (Slot: Secondary, Restrictions: Shield Only).
# Merged into every profile catalog; ranked by AC for Secondary shields.
SHIELD_AUG_URL = (
    "https://www.raidloot.com/items?type=Aug_Shield&augslot=7%2C8&order=AC"
)

# Raidloot filter URLs (Dex / INT / WIS type 7/8 catalogs)
RAIDLOOT_URLS: dict[ProfileId, str] = {
    "dex": (
        "https://www.raidloot.com/items/augs?augslot=7%2C8&level=&source="
        "&AC=0&HP=0&Mana=0&End=0&ATK=0&HSta=0&HStr=0&HDex=30&HAgi=0&HWis=0"
        "&HInt=0&HCha=0&Clrv=0&Heal=0&Nuke=0"
    ),
    "int": (
        "https://www.raidloot.com/items/augs?augslot=7%2C8&level=&source="
        "&AC=0&HP=0&Mana=0&End=0&ATK=0&HSta=0&HStr=0&HDex=&HAgi=0&HWis=0"
        "&HInt=35&HCha=0&Clrv=0&Heal=0&Nuke=0"
    ),
    "wis": (
        "https://www.raidloot.com/items/augs?augslot=7%2C8&level=&source="
        "&AC=0&HP=0&Mana=0&End=0&ATK=0&HSta=0&HStr=0&HDex=&HAgi=0&HWis=35"
        "&HInt=0&HCha=0&Clrv=0&Heal=0&Nuke=0"
    ),
}

# Class abbreviations → profile (from Example notes).
# Melee: WAR, PAL, SHD, MNK, RNG, ROG, BST, BRD (+ BER)
# Casters: ENC, WIZ, MAG, NEC
# Priests: SHM, CLR, DRU
CLASS_TO_PROFILE: dict[str, ProfileId] = {
    "WAR": "dex",
    "PAL": "dex",
    "SHD": "dex",
    "MNK": "dex",
    "RNG": "dex",
    "ROG": "dex",
    "BST": "dex",
    "BRD": "dex",
    "BER": "dex",
    "ENC": "int",
    "WIZ": "int",
    "MAG": "int",
    "NEC": "int",
    "SHM": "wis",
    "CLR": "wis",
    "DRU": "wis",
}

# Feet Slot2: prefer highest AC type 7/8 (not focus heroic) for these classes.
FEET_HIGH_AC_CLASSES: frozenset[str] = frozenset(
    {"WAR", "MNK", "RNG", "BST", "BRD"}
)

ARTISANS_PRIZE_ID = 88785
ARTISANS_PRIZE_NAME = "Artisan's Prize"


@dataclass(frozen=True)
class ProfileInfo:
    profile_id: ProfileId
    label: str
    focus_stat: str
    url: str


def normalize_profile(value: str | None) -> ProfileId:
    if not value:
        return "dex"
    key = value.strip().lower()
    if key in PROFILES:
        return key  # type: ignore[return-value]
    raise ValueError(f"Unknown profile: {value!r} (expected dex, int, or wis)")


def uses_feet_high_ac(class_abbr: str | None) -> bool:
    """True when Feet uses the AC-heavy slot overlay (WAR/MNK/RNG/BST/BRD)."""
    if not class_abbr:
        return False
    # Prefer overlay table when available; fall back to the hardcoded set.
    try:
        from eq_augs.weights import uses_feet_overlay

        return uses_feet_overlay(class_abbr)
    except Exception:
        return class_abbr.strip().upper() in FEET_HIGH_AC_CLASSES


def profile_for_class(class_abbr: str | None) -> ProfileId | None:
    if not class_abbr:
        return None
    return CLASS_TO_PROFILE.get(class_abbr.strip().upper())


def profile_info(profile_id: ProfileId) -> ProfileInfo:
    return ProfileInfo(
        profile_id=profile_id,
        label=PROFILE_LABELS[profile_id],
        focus_stat=PROFILE_FOCUS_STAT[profile_id],
        url=RAIDLOOT_URLS[profile_id],
    )
