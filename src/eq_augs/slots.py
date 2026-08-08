"""Equipment slot layout (aligned with Inventory Parser conventions)."""

from __future__ import annotations

# Slots shown on the character model (armor view).
VISIBLE_SLOTS: tuple[str, ...] = (
    "Arms",
    "Chest",
    "Feet",
    "Hands",
    "Head",
    "Legs",
    "Wrist-1",
    "Wrist-2",
    "Primary",
    "Secondary",
)

# Equipped slots not on the visible model (jewelry, cloak, etc.).
NON_VISIBLE_SLOTS: tuple[str, ...] = (
    "Back",
    "Charm",
    "Ear-1",
    "Ear-2",
    "Face",
    "Fingers-1",
    "Fingers-2",
    "Neck",
    "Range",
    "Shoulders",
    "Waist",
)

# All report slots: visible first, then non-visible.
REPORT_SLOTS: tuple[str, ...] = VISIBLE_SLOTS + NON_VISIBLE_SLOTS

# Gear-slot bases that appear as top-level locations in inventory dumps.
EQUIPMENT_SLOT_BASES: frozenset[str] = frozenset(
    {
        "Charm",
        "Ear",
        "Head",
        "Face",
        "Neck",
        "Shoulders",
        "Arms",
        "Back",
        "Wrist",
        "Range",
        "Hands",
        "Primary",
        "Secondary",
        "Fingers",
        "Chest",
        "Legs",
        "Feet",
        "Waist",
        "Power Source",
        "Ammo",
    }
)

# Canonical gear slots used when normalizing raidloot "All except …" strings.
ALL_GEAR_SLOTS: frozenset[str] = frozenset(
    {
        "Charm",
        "Ear",
        "Head",
        "Face",
        "Neck",
        "Shoulders",
        "Arms",
        "Back",
        "Wrist",
        "Range",
        "Hands",
        "Primary",
        "Secondary",
        "Fingers",
        "Chest",
        "Legs",
        "Feet",
        "Waist",
        "Power Source",
        "Ammo",
    }
)

# Report keys that map to the Ear base for slot-restriction checks.
EAR_REPORT_SLOTS: frozenset[str] = frozenset({"Ear-1", "Ear-2", "Ear"})

# Range and Charm first — few augs fit those holes, so their BiS is claimed before
# general slots. Feet joins that priority set when the high-AC overlay applies
# (see ``priority_aug_slots``). Remaining order follows the report layout.
PRIORITY_AUG_SLOTS: tuple[str, ...] = ("Range", "Charm")

AUG_ASSIGNMENT_ORDER: tuple[str, ...] = PRIORITY_AUG_SLOTS + tuple(
    s for s in REPORT_SLOTS if s not in PRIORITY_AUG_SLOTS
)


def priority_aug_slots(class_abbr: str | None = None) -> tuple[str, ...]:
    """
    Slots that claim BiS first because fewer augs fit them.

    Always Range then Charm. Feet is included when the class uses the Feet
    high-AC overlay (WAR/MNK/RNG/BST/BRD).
    """
    if class_abbr:
        from eq_augs.weights import uses_feet_overlay

        if uses_feet_overlay(class_abbr):
            return ("Range", "Charm", "Feet")
    return PRIORITY_AUG_SLOTS


def aug_assignment_order(class_abbr: str | None = None) -> tuple[str, ...]:
    """Full slot claim order: priority holes first, then remaining report slots."""
    priority = priority_aug_slots(class_abbr)
    rest = tuple(s for s in REPORT_SLOTS if s not in priority)
    return priority + rest

