"""Compare equipped type 7/8 augs against raidloot BiS as a whole loadout."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from eq_augs.eqresource_augs import resolve_eqresource_augs
from eq_augs.parser import (
    InventoryData,
    Slot2Aug,
    collect_owned_item_ids,
    extract_slot2_augs,
    parent_name_is_shield,
)
from eq_augs.profiles import (
    ARTISANS_PRIZE_ID,
    ARTISANS_PRIZE_NAME,
    PROFILE_FOCUS_LABEL,
    ProfileId,
)
from eq_augs.raidloot import AugCandidate, CatalogResult, augs_for_slot
from eq_augs.slots import (
    AUG_ASSIGNMENT_ORDER,
    EAR_REPORT_SLOTS,
    PRIORITY_AUG_SLOTS,
    REPORT_SLOTS,
)
from eq_augs.weights import (
    rank_key,
    resolve_weights,
    score_aug,
    score_delta_contributors,
    uses_feet_overlay,
)

SlotStatus = Literal["empty", "bis", "upgrade", "unknown", "no_fit"]

# Rows included in HTML/Excel reports. Ignored weapon slots (`no_fit`) are omitted.
REPORT_ROW_STATUSES: frozenset[str] = frozenset(
    {"upgrade", "empty", "unknown", "bis"}
)

# Statuses that show a non-blank Upgrade-to recommendation.
NEEDS_UPGRADE_STATUSES: frozenset[str] = frozenset({"upgrade", "empty", "unknown"})


@dataclass(frozen=True)
class Slot2Comparison:
    gear_slot: str
    current_name: str | None
    current_id: int | None
    recommended_name: str | None
    recommended_id: int | None
    recommended_focus: int | None
    status: SlotStatus
    note: str = ""
    recommended_owned: bool | None = None
    recommended_expansion: str | None = None
    move_from_slot: str | None = None


@dataclass(frozen=True)
class FarmListEntry:
    character: str
    server: str
    persona_key: str
    gear_slot: str
    name: str
    item_id: int
    expansion: str | None = None


@dataclass
class CharacterSlot2Report:
    character: str
    server: str
    class_abbr: str | None
    profile: ProfileId
    filepath: str
    comparisons: list[Slot2Comparison]
    owned_item_ids: set[int] = field(default_factory=set)


def _is_ear_slot(gear_slot: str) -> bool:
    return gear_slot in EAR_REPORT_SLOTS or gear_slot.startswith("Ear")


def _is_feet_slot(gear_slot: str) -> bool:
    return gear_slot == "Feet"


def _is_secondary_shield(gear_slot: str, parent_name: str | None) -> bool:
    return gear_slot == "Secondary" and parent_name_is_shield(parent_name)


def _weapon_slot_skip_note(gear_slot: str, parent_name: str | None) -> str | None:
    """Primary always skipped; Secondary skipped unless parent is a shield."""
    if gear_slot == "Primary":
        return "Primary weapons ignored"
    if gear_slot == "Secondary" and not parent_name_is_shield(parent_name):
        return "Secondary weapons ignored (shield Secondary only)"
    return None


def _sort_key_for_slot(
    gear_slot: str,
    class_abbr: str | None,
    *,
    secondary_is_shield: bool = False,
    profile: ProfileId | None = None,
):
    def _key(a: AugCandidate):
        return rank_key(
            a,
            class_abbr,
            gear_slot,
            secondary_is_shield=secondary_is_shield,
            profile=profile or a.profile,
        )

    return _key


def _aug_rank_tuple(
    aug: AugCandidate,
    gear_slot: str,
    class_abbr: str | None,
    *,
    secondary_is_shield: bool = False,
    profile: ProfileId | None = None,
) -> tuple:
    return rank_key(
        aug,
        class_abbr,
        gear_slot,
        secondary_is_shield=secondary_is_shield,
        profile=profile or aug.profile,
    )


def _uses_ac_primary(
    gear_slot: str,
    class_abbr: str | None,
    *,
    secondary_is_shield: bool = False,
) -> bool:
    if secondary_is_shield and gear_slot == "Secondary":
        return True
    if _is_feet_slot(gear_slot) and uses_feet_overlay(class_abbr):
        return True
    return False


def _signed_stat(delta: int) -> str:
    return f"+{delta}" if delta >= 0 else str(delta)


def upgrade_stat_delta_note(
    current_aug: AugCandidate | None,
    recommended: AugCandidate,
    gear_slot: str,
    class_abbr: str | None,
    *,
    secondary_is_shield: bool = False,
    profile: ProfileId = "dex",
) -> str:
    """Format score contributors + HDex/HInt/HWis + AC/HP gains."""
    weights = resolve_weights(
        class_abbr,
        gear_slot,
        secondary_is_shield=secondary_is_shield,
        profile=profile,
    )
    cur_score = score_aug(current_aug, weights) if current_aug else 0.0
    rec_score = score_aug(recommended, weights)
    d_score = rec_score - cur_score
    contributors = score_delta_contributors(
        current_aug, recommended, weights, top_n=3
    )
    contrib_txt = ", ".join(label for label, _ in contributors) if contributors else ""

    cur_focus = current_aug.focus_heroic if current_aug else 0
    cur_ac = current_aug.ac if current_aug else 0
    cur_hp = current_aug.hp if current_aug else 0
    d_focus = recommended.focus_heroic - cur_focus
    d_ac = recommended.ac - cur_ac
    d_hp = recommended.hp - cur_hp
    focus_label = PROFILE_FOCUS_LABEL.get(profile, "HDex")

    parts: list[str] = []
    score_bit = f"{_signed_stat(int(round(d_score)))} score"
    if contrib_txt:
        score_bit = f"{score_bit} ({contrib_txt})"
    parts.append(score_bit)

    if _uses_ac_primary(
        gear_slot, class_abbr, secondary_is_shield=secondary_is_shield
    ):
        parts.append(f"{_signed_stat(d_ac)} AC")
        if d_hp:
            parts.append(f"{_signed_stat(d_hp)} HP")
        if d_focus:
            parts.append(f"{_signed_stat(d_focus)} {focus_label}")
    else:
        parts.append(f"{_signed_stat(d_focus)} {focus_label}")
        if d_hp:
            parts.append(f"{_signed_stat(d_hp)} HP")
        if d_ac:
            parts.append(f"{_signed_stat(d_ac)} AC")
    return ", ".join(parts)


def _prize_candidate(catalog: list[AugCandidate]) -> AugCandidate:
    prize = next((a for a in catalog if a.item_id == ARTISANS_PRIZE_ID), None)
    if prize is not None:
        return prize
    from eq_augs.aug_stats import artisans_prize_stats, legacy_from_stats

    profile: ProfileId = catalog[0].profile if catalog else "dex"
    stats = artisans_prize_stats()
    focus, ac, hp, atk = legacy_from_stats(stats, profile)
    return AugCandidate(
        item_id=ARTISANS_PRIZE_ID,
        name=ARTISANS_PRIZE_NAME,
        profile=profile,
        focus_heroic=focus or 150,
        ac=ac,
        hp=hp,
        atk=atk,
        slot_text="Ear",
        allowed_bases=frozenset({"Ear"}),
        ear_only=True,
        lore=True,
        stats=stats,
    )


def _current_matches_aug(current: Slot2Aug, aug: AugCandidate) -> bool:
    if current.item_id is not None and current.item_id == aug.item_id:
        return True
    if current.name and current.name.casefold() == aug.name.casefold():
        return True
    return False


def _catalog_aug_for_id(
    catalog: list[AugCandidate], item_id: int | None
) -> AugCandidate | None:
    if item_id is None:
        return None
    return next((a for a in catalog if a.item_id == item_id), None)


def _lookup_current_aug(
    catalog: list[AugCandidate],
    item_id: int | None,
    *,
    external_augs: dict[int, AugCandidate] | None = None,
) -> AugCandidate | None:
    found = _catalog_aug_for_id(catalog, item_id)
    if found is not None:
        return found
    if item_id is None or not external_augs:
        return None
    return external_augs.get(item_id)


def pick_best_for_slot(
    gear_slot: str,
    catalog: list[AugCandidate],
    *,
    unavailable_ids: set[int],
    artisans_prize_owned: bool,
    class_abbr: str | None = None,
    secondary_is_shield: bool = False,
) -> AugCandidate | None:
    """Best aug for one slot, skipping unavailable item ids."""
    if gear_slot == "Primary":
        return None
    if gear_slot == "Secondary" and not secondary_is_shield:
        return None

    if artisans_prize_owned and _is_ear_slot(gear_slot):
        prize = _prize_candidate(catalog)
        if prize.item_id not in unavailable_ids:
            return prize

    fitted = [
        a
        for a in augs_for_slot(catalog, gear_slot)
        if a.item_id != ARTISANS_PRIZE_ID and a.item_id not in unavailable_ids
    ]
    if gear_slot == "Secondary" and secondary_is_shield:
        fitted = [a for a in fitted if a.shield_only]
    else:
        fitted = [a for a in fitted if not a.shield_only]

    if not fitted:
        return None
    fitted.sort(
        key=_sort_key_for_slot(
            gear_slot, class_abbr, secondary_is_shield=secondary_is_shield
        )
    )
    return fitted[0]


def recommend_for_slot(
    gear_slot: str,
    catalog: list[AugCandidate],
    *,
    artisans_prize_owned: bool,
    class_abbr: str | None = None,
    used_lore_ids: set[int] | None = None,
    unavailable_ids: set[int] | None = None,
    secondary_is_shield: bool = False,
) -> AugCandidate | None:
    """Pick the best type 7/8 aug for a gear slot (optional exclusions)."""
    blocked = set(unavailable_ids or ())
    if used_lore_ids:
        blocked |= set(used_lore_ids)
    return pick_best_for_slot(
        gear_slot,
        catalog,
        unavailable_ids=blocked,
        artisans_prize_owned=artisans_prize_owned,
        class_abbr=class_abbr,
        secondary_is_shield=secondary_is_shield,
    )


def _slot_order(gear_slots: list[str]) -> list[str]:
    present = set(gear_slots)
    order = [s for s in AUG_ASSIGNMENT_ORDER if s in present]
    for slot in gear_slots:
        if slot not in order:
            order.append(slot)
    return order


def build_ideal_loadout(
    gear_slots: list[str],
    catalog: list[AugCandidate],
    *,
    artisans_prize_owned: bool,
    class_abbr: str | None = None,
    shield_secondary: bool = False,
) -> dict[str, AugCandidate | None]:
    """Absolute BiS unique assignment ignoring what is currently equipped."""
    order = _slot_order(gear_slots)
    unavailable: set[int] = set()
    ideal: dict[str, AugCandidate | None] = {}

    # Empty-first is irrelevant with no currents; use report order.
    # Prefer putting Artisan's Prize on an Ear when owned.
    if artisans_prize_owned:
        for slot in order:
            if not _is_ear_slot(slot):
                continue
            prize = _prize_candidate(catalog)
            ideal[slot] = prize
            unavailable.add(prize.item_id)
            break

    for slot in order:
        if slot in ideal:
            continue
        pick = pick_best_for_slot(
            slot,
            catalog,
            unavailable_ids=unavailable,
            artisans_prize_owned=False,  # prize already placed if owned
            class_abbr=class_abbr,
            secondary_is_shield=shield_secondary and slot == "Secondary",
        )
        ideal[slot] = pick
        if pick is not None:
            unavailable.add(pick.item_id)
    return ideal


def assign_slot_recommendations(
    gear_slots: list[str],
    catalog: list[AugCandidate],
    *,
    artisans_prize_owned: bool,
    class_abbr: str | None = None,
    shield_secondary: bool = False,
    current_by_slot: dict[str, Slot2Aug] | None = None,
) -> dict[str, AugCandidate | None]:
    """
    Recommend only ideal BiS augs the character is missing.

    1. Build the ideal unique loadout (Range/Charm claimed first).
    2. Priority slots (Range, Charm) pull their ideal aug even when it is
       currently equipped in another slot (suggest a move).
    3. Other slots keep an equipped ideal piece unless it was claimed above.
    4. Remaining missing ideal augs fill empty holes first, then non-ideal
       currents — priority slots before general slots.
    5. Never recommend an aug worse than the slot's current (by slot rank key).
    """
    current_by_slot = current_by_slot or {}
    order = _slot_order(gear_slots)
    priority = {s for s in PRIORITY_AUG_SLOTS if s in order}

    ideal = build_ideal_loadout(
        gear_slots,
        catalog,
        artisans_prize_owned=artisans_prize_owned,
        class_abbr=class_abbr,
        shield_secondary=shield_secondary,
    )
    ideal_ids = {a.item_id for a in ideal.values() if a is not None}

    equipped_ids = {
        cur.item_id
        for cur in current_by_slot.values()
        if cur is not None and cur.item_id is not None and cur.item_id > 0
    }
    owned_ideal_ids = ideal_ids & equipped_ids
    missing_ideal = [
        aug
        for aug in ideal.values()
        if aug is not None and aug.item_id not in owned_ideal_ids
    ]
    missing_ideal.sort(
        key=lambda a: rank_key(a, class_abbr, "Head", profile=a.profile)
    )

    assigned: dict[str, AugCandidate | None] = {}
    claimed_ids: set[int] = set()

    def _equipped_slot_for(item_id: int) -> str | None:
        for other, cur in current_by_slot.items():
            if cur is not None and cur.item_id == item_id:
                return other
        return None

    # Priority slots claim their ideal BiS, including moves from other slots.
    for slot in PRIORITY_AUG_SLOTS:
        if slot not in order:
            continue
        ideal_aug = ideal.get(slot)
        if ideal_aug is None:
            continue
        cur = current_by_slot.get(slot)
        if cur is not None and cur.item_id == ideal_aug.item_id:
            assigned[slot] = ideal_aug
            claimed_ids.add(ideal_aug.item_id)
            continue
        source = _equipped_slot_for(ideal_aug.item_id)
        if source is not None:
            assigned[slot] = ideal_aug
            claimed_ids.add(ideal_aug.item_id)

    # Non-priority slots claim their ideal when it sits on Range/Charm and that
    # priority slot does not need it as its own ideal (displaced piece moves down).
    for slot in order:
        if slot in assigned or slot in PRIORITY_AUG_SLOTS:
            continue
        ideal_aug = ideal.get(slot)
        if ideal_aug is None or ideal_aug.item_id in claimed_ids:
            continue
        source = _equipped_slot_for(ideal_aug.item_id)
        if source is None or source == slot:
            continue
        if source not in PRIORITY_AUG_SLOTS:
            continue
        source_ideal = ideal.get(source)
        # Do not steal a piece that is the source slot's own ideal.
        if source_ideal is not None and source_ideal.item_id == ideal_aug.item_id:
            continue
        assigned[slot] = ideal_aug
        claimed_ids.add(ideal_aug.item_id)

    # Keep ideal pieces where they already sit — except priority slots holding a
    # non-ideal piece (those stay free for a better Range/Charm BiS).
    for slot in order:
        if slot in assigned:
            continue
        cur = current_by_slot.get(slot)
        if cur is None or cur.item_id is None:
            continue
        if cur.item_id not in ideal_ids or cur.item_id in claimed_ids:
            continue
        slot_ideal = ideal.get(slot)
        if slot in PRIORITY_AUG_SLOTS and (
            slot_ideal is None or cur.item_id != slot_ideal.item_id
        ):
            continue
        keep = _catalog_aug_for_id(catalog, cur.item_id) or slot_ideal
        if keep is None:
            keep = next(
                (a for a in ideal.values() if a and a.item_id == cur.item_id),
                None,
            )
        assigned[slot] = keep
        if keep is not None:
            claimed_ids.add(keep.item_id)

    owned_ideal_ids |= claimed_ids

    # Place missing ideal augs into needy slots (priority → empty → rest).
    needy = [s for s in order if s not in assigned]
    needy.sort(
        key=lambda s: (
            0 if s in priority else 1,
            0
            if (current_by_slot.get(s) is None or current_by_slot[s].item_id is None)
            else 1,
            order.index(s),
        )
    )

    still_missing = [a for a in missing_ideal if a.item_id not in claimed_ids]
    used_missing: set[int] = set()

    for slot in needy:
        secondary = shield_secondary and slot == "Secondary"
        cur = current_by_slot.get(slot)
        placed: AugCandidate | None = None
        for aug in still_missing:
            if aug.item_id in used_missing or aug.item_id in claimed_ids:
                continue
            if not aug.fits_gear_slot(slot):
                continue
            if secondary and not aug.shield_only:
                continue
            if not secondary and aug.shield_only:
                continue
            if aug.item_id == ARTISANS_PRIZE_ID and not artisans_prize_owned:
                continue
            if cur is not None and cur.item_id is not None:
                cur_aug = _catalog_aug_for_id(catalog, cur.item_id)
                if cur_aug is not None:
                    if _aug_rank_tuple(
                        aug, slot, class_abbr, secondary_is_shield=secondary
                    ) > _aug_rank_tuple(
                        cur_aug, slot, class_abbr, secondary_is_shield=secondary
                    ):
                        continue
            placed = aug
            break

        if placed is not None:
            assigned[slot] = placed
            used_missing.add(placed.item_id)
            claimed_ids.add(placed.item_id)
        elif cur is not None and cur.item_id is not None:
            if cur.item_id in claimed_ids:
                # Current was moved elsewhere — recommend next best free pick.
                assigned[slot] = pick_best_for_slot(
                    slot,
                    catalog,
                    unavailable_ids=set(claimed_ids),
                    artisans_prize_owned=artisans_prize_owned,
                    class_abbr=class_abbr,
                    secondary_is_shield=secondary,
                )
                replacement = assigned[slot]
                if replacement is not None:
                    claimed_ids.add(replacement.item_id)
            else:
                assigned[slot] = _catalog_aug_for_id(catalog, cur.item_id)
        else:
            assigned[slot] = None

    return assigned


def classify_status(
    current: Slot2Aug,
    recommended: AugCandidate | None,
) -> tuple[SlotStatus, str]:
    skip = _weapon_slot_skip_note(current.gear_slot, current.parent_name)
    if skip is not None:
        return "no_fit", skip

    if current.name is None or current.item_id is None:
        if recommended is None:
            return "no_fit", "Empty; no type 7/8 aug fits this slot"
        return "empty", "Empty Slot2"

    if recommended is None:
        return "no_fit", "Current aug present; no catalog aug fits this slot"

    if current.item_id == recommended.item_id or (
        current.name.casefold() == recommended.name.casefold()
    ):
        return "bis", "Matches recommended"

    if current.item_id == ARTISANS_PRIZE_ID and _is_ear_slot(current.gear_slot):
        return "bis", "Artisan's Prize (Ear BiS)"

    return "upgrade", f"Recommended: {recommended.name}"


def _finalize_comparison(
    current: Slot2Aug,
    recommended: AugCandidate | None,
    catalog: list[AugCandidate],
    class_abbr: str | None,
    *,
    profile: ProfileId = "dex",
    move_from_slot: str | None = None,
    moved_to_slot: str | None = None,
    external_augs: dict[int, AugCandidate] | None = None,
    owned_item_ids: set[int] | None = None,
) -> Slot2Comparison:
    status, note = classify_status(current, recommended)
    secondary = _is_secondary_shield(current.gear_slot, current.parent_name)
    cur_aug = _lookup_current_aug(
        catalog, current.item_id, external_augs=external_augs
    )
    stats_from_eqr = (
        cur_aug is not None
        and current.item_id is not None
        and not any(a.item_id == current.item_id for a in catalog)
        and (cur_aug.source or "").casefold().startswith("eq resource")
    )

    if (
        status == "upgrade"
        and current.item_id is not None
        and cur_aug is None
        and (current.name or "").casefold() != ARTISANS_PRIZE_NAME.casefold()
    ):
        status = "unknown"
        note = "Current aug not in raidloot catalog (EQ Resource miss)"

    # Guard: never list an upgrade that ranks worse than current.
    if status == "upgrade" and recommended is not None and cur_aug is not None:
        if _aug_rank_tuple(
            recommended,
            current.gear_slot,
            class_abbr,
            secondary_is_shield=secondary,
        ) > _aug_rank_tuple(
            cur_aug,
            current.gear_slot,
            class_abbr,
            secondary_is_shield=secondary,
        ):
            status = "bis"
            note = "Current is better than remaining missing BiS options"
            recommended = cur_aug
            move_from_slot = None
            stats_from_eqr = False

    # Lead note with Focus/AC/HP gain when an upgrade is recommended.
    if status in ("upgrade", "empty") and recommended is not None:
        delta_current = cur_aug if status == "upgrade" else None
        if (
            status == "upgrade"
            and delta_current is None
            and (current.name or "").casefold() == ARTISANS_PRIZE_NAME.casefold()
        ):
            delta_current = _prize_candidate(catalog)
        note = upgrade_stat_delta_note(
            delta_current,
            recommended,
            current.gear_slot,
            class_abbr,
            secondary_is_shield=secondary,
            profile=profile,
        )

    move_bits: list[str] = []
    if move_from_slot and status in ("upgrade", "empty", "unknown"):
        move_bits.append(f"Move from {move_from_slot}")
    if moved_to_slot and status in ("upgrade", "empty", "unknown", "bis"):
        label = current.name or "Current aug"
        move_bits.append(f"Move {label} to {moved_to_slot}")
    if move_bits:
        move_txt = "; ".join(move_bits)
        note = f"{move_txt}; {note}" if note else move_txt

    if stats_from_eqr and status in ("upgrade", "empty", "bis"):
        eqr_bit = "stats via EQ Resource"
        note = f"{note}; {eqr_bit}" if note else eqr_bit

    extras: list[str] = []
    if recommended is not None and recommended.lore:
        extras.append("Lore — unique equip")
    if recommended is not None and recommended.shield_only:
        extras.append("Shield Only Secondary aug")
    if (
        recommended is not None
        and _is_feet_slot(current.gear_slot)
        and uses_feet_overlay(class_abbr)
    ):
        extras.append(
            f"Highest AC for Feet ({class_abbr.strip().upper()}): {recommended.ac} AC"
        )
    if extras and status != "bis":
        extra = "; ".join(extras)
        note = f"{note}; {extra}" if note else extra

    if current.dump_slot == 4 and current.gear_slot == "Range":
        bow_note = "Range Slot1–4 + name has bow → type 7/8 in Slot4"
        note = f"{note}; {bow_note}" if note else bow_note
    elif current.socket_map_hit and current.dump_slot != 2:
        slot_note = f"type 7/8 in Slot{current.dump_slot}"
        note = f"{note}; {slot_note}" if note else slot_note
    elif (
        not current.socket_map_hit
        and current.parent_id
        and current.parent_id > 0
        and current.gear_slot not in ("Primary",)
        and not (
            current.gear_slot == "Secondary"
            and not parent_name_is_shield(current.parent_name)
        )
    ):
        miss_note = (
            f"type 7/8 via Slot{current.dump_slot} heuristic (no socket map)"
        )
        note = f"{note}; {miss_note}" if note else miss_note

    focus_value: int | None = None
    if recommended is not None:
        if recommended.shield_only and current.gear_slot == "Secondary":
            focus_value = recommended.ac
        elif _is_feet_slot(current.gear_slot) and uses_feet_overlay(class_abbr):
            focus_value = recommended.ac
        else:
            focus_value = recommended.focus_heroic

    rec_owned: bool | None = None
    if recommended is not None and recommended.item_id > 0:
        owned = owned_item_ids or set()
        # Equipped-elsewhere moves are owned even if the ID check were missed.
        rec_owned = recommended.item_id in owned or move_from_slot is not None

    return Slot2Comparison(
        gear_slot=current.gear_slot,
        current_name=current.name,
        current_id=current.item_id,
        recommended_name=recommended.name if recommended else None,
        recommended_id=recommended.item_id if recommended else None,
        recommended_focus=focus_value,
        status=status,
        note=note,
        recommended_owned=rec_owned,
        move_from_slot=move_from_slot
        if status in ("upgrade", "empty", "unknown")
        else None,
    )


def _move_maps(
    assigned: dict[str, AugCandidate | None],
    current_by_slot: dict[str, Slot2Aug],
) -> tuple[dict[str, str], dict[str, str]]:
    """Map dest→source and donor→dest when a recommendation is currently equipped elsewhere."""
    move_from: dict[str, str] = {}
    moved_to: dict[str, str] = {}
    for slot, rec in assigned.items():
        if rec is None:
            continue
        cur = current_by_slot.get(slot)
        if cur is not None and cur.item_id == rec.item_id:
            continue
        for other, other_cur in current_by_slot.items():
            if other == slot or other_cur is None or other_cur.item_id is None:
                continue
            if other_cur.item_id == rec.item_id:
                move_from[slot] = other
                moved_to[other] = slot
                break
    return move_from, moved_to


def _priority_move_maps(
    assigned: dict[str, AugCandidate | None],
    current_by_slot: dict[str, Slot2Aug],
) -> tuple[dict[str, str], dict[str, str]]:
    """Backward-compatible alias for :func:`_move_maps`."""
    return _move_maps(assigned, current_by_slot)


def compare_character(
    data: InventoryData,
    catalog_result: CatalogResult,
    *,
    artisans_prize_owned: bool,
    profile: ProfileId | None = None,
    class_abbr: str | None = None,
    type78_slot_by_parent_id: dict[int, int | None] | None = None,
    eqr_aug_html_by_id: dict[int, str] | None = None,
    fetch_eqr_augs: bool = True,
) -> CharacterSlot2Report:
    """Build per-slot comparisons for one character (missing-BiS loadout)."""
    used_profile = profile or catalog_result.profile
    used_class = class_abbr if class_abbr is not None else data.class_abbr
    slot_map: dict[int, int] | None = None
    if type78_slot_by_parent_id is not None:
        slot_map = {
            iid: slot
            for iid, slot in type78_slot_by_parent_id.items()
            if slot is not None
        }
    slot2 = extract_slot2_augs(data, type78_slot_by_parent_id=slot_map)
    by_slot = {s.gear_slot: s for s in slot2}
    catalog = catalog_result.augs
    catalog_ids = {a.item_id for a in catalog}
    owned_ids = collect_owned_item_ids(data)
    if artisans_prize_owned:
        owned_ids = set(owned_ids)
        owned_ids.add(ARTISANS_PRIZE_ID)

    missing_ids: list[int] = []
    name_hints: dict[int, str] = {}
    for s in slot2:
        if s.item_id is None or s.item_id <= 0:
            continue
        if s.item_id in catalog_ids:
            continue
        if (s.name or "").casefold() == ARTISANS_PRIZE_NAME.casefold():
            continue
        missing_ids.append(s.item_id)
        if s.name:
            name_hints[s.item_id] = s.name
    external_augs = resolve_eqresource_augs(
        missing_ids,
        used_profile,
        html_overrides=eqr_aug_html_by_id,
        name_hints=name_hints,
        allow_network=fetch_eqr_augs,
    )

    gear_slots = [s for s in REPORT_SLOTS if s in by_slot]
    for slot in by_slot:
        if slot not in gear_slots:
            gear_slots.append(slot)

    secondary = by_slot.get("Secondary")
    shield_secondary = bool(
        secondary and _is_secondary_shield(secondary.gear_slot, secondary.parent_name)
    )

    assigned = assign_slot_recommendations(
        gear_slots,
        catalog,
        artisans_prize_owned=artisans_prize_owned,
        class_abbr=used_class,
        shield_secondary=shield_secondary,
        current_by_slot=by_slot,
    )
    move_from, moved_to = _move_maps(assigned, by_slot)

    comparisons = [
        _finalize_comparison(
            by_slot[slot],
            assigned.get(slot),
            catalog,
            used_class,
            profile=used_profile,
            move_from_slot=move_from.get(slot),
            moved_to_slot=moved_to.get(slot),
            external_augs=external_augs,
            owned_item_ids=owned_ids,
        )
        for slot in gear_slots
        if slot in by_slot
    ]

    order = {s: i for i, s in enumerate(REPORT_SLOTS)}
    comparisons.sort(key=lambda c: (order.get(c.gear_slot, 1000), c.gear_slot))

    return CharacterSlot2Report(
        character=data.character,
        server=data.server,
        class_abbr=used_class,
        profile=used_profile,
        filepath=data.filepath,
        comparisons=comparisons,
        owned_item_ids=owned_ids,
    )
