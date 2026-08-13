"""Assemble Slot2 aug report data once for Excel and HTML exporters."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from eq_augs.anniversary import filter_anniversary_augs
from eq_augs.chest_class import profile_from_class, resolve_classes_for_inventories
from eq_augs.compare import (
    CharacterSlot2Report,
    FarmListEntry,
    NEEDS_UPGRADE_STATUSES,
    Slot2Comparison,
    compare_character,
)
from eq_augs.eqresource_augs import resolve_item_expansions
from eq_augs.item_sockets import resolve_type78_slots
from eq_augs.parser import (
    InventoryData,
    collect_equipped_parent_ids,
    discover_inventory_files,
    parse_inventory_file,
)
from eq_augs.profiles import PROFILE_LABELS, ProfileId, normalize_profile, profile_for_class
from eq_augs.raidloot import AugCandidate, CatalogResult, fetch_catalog
from eq_augs.roster import RosterEntry, build_roster, export_prefix_from_roster, persona_key

ProgressFn = Callable[[dict], None]

# Stage fraction ranges for determinate GUI progress (write stage is 0.95–1.0 in web_api).
_PROGRESS_PARSE = (0.00, 0.05)
_PROGRESS_CLASSES = (0.05, 0.12)
_PROGRESS_SOCKETS = (0.12, 0.45)
_PROGRESS_CATALOG = (0.45, 0.65)
_PROGRESS_COMPARE = (0.65, 0.88)
_PROGRESS_EXPANSIONS = (0.88, 0.95)


def report_progress(
    on_progress: ProgressFn | None,
    message: str,
    start: float,
    end: float,
    i: int = 1,
    n: int = 1,
) -> None:
    """Emit a progress payload with fraction in ``[start, end]`` for step ``i`` of ``n``."""
    if on_progress is None:
        return
    if n <= 0:
        fraction = end
    else:
        fraction = start + (end - start) * (i / n)
    on_progress(
        {
            "message": message,
            "fraction": min(1.0, max(0.0, fraction)),
        }
    )


def _range_item_progress(
    on_progress: ProgressFn | None,
    message: str,
    start: float,
    end: float,
) -> Callable[[int, int], None] | None:
    if on_progress is None:
        return None

    def _cb(done: int, total: int) -> None:
        if total <= 0:
            report_progress(on_progress, message, start, end, 1, 1)
        else:
            report_progress(
                on_progress,
                f"{message} ({done}/{total})",
                start,
                end,
                done,
                total,
            )

    return _cb


@dataclass
class ExportBundle:
    profile: ProfileId
    profile_label: str
    artisans_prize_owned: bool
    catalog: CatalogResult
    characters: list[CharacterSlot2Report] = field(default_factory=list)
    ranked_augs: list[AugCandidate] = field(default_factory=list)
    farm_list: list[FarmListEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    server: str = ""
    export_prefix: str = "Team"
    show_server_in_columns: bool = False
    roster: list[RosterEntry] = field(default_factory=list)
    include_anniversary: bool = False


def build_farm_list(
    characters: list[CharacterSlot2Report],
    roster: list[RosterEntry],
) -> list[FarmListEntry]:
    """Recommended upgrades not present anywhere in that character's inventory."""
    entries: list[FarmListEntry] = []
    for i, ch in enumerate(characters):
        pk = (
            roster[i].persona_key
            if i < len(roster)
            else persona_key(ch.character, ch.server, ch.class_abbr)
        )
        for cmp_ in ch.comparisons:
            if cmp_.status not in NEEDS_UPGRADE_STATUSES:
                continue
            if not cmp_.recommended_id or not cmp_.recommended_name:
                continue
            if cmp_.recommended_owned:
                continue
            entries.append(
                FarmListEntry(
                    character=ch.character,
                    server=ch.server,
                    persona_key=pk,
                    gear_slot=cmp_.gear_slot,
                    name=cmp_.recommended_name,
                    item_id=cmp_.recommended_id,
                    expansion=cmp_.recommended_expansion,
                    craft_component_name=cmp_.craft_component_name,
                    craft_component_id=cmp_.craft_component_id,
                    craft_component_owned=cmp_.craft_component_owned,
                )
            )
    return entries


def apply_expansions_to_characters(
    characters: list[CharacterSlot2Report],
    expansions: dict[int, str],
) -> list[CharacterSlot2Report]:
    """Attach expansion names onto recommended comparisons (frozen dataclasses)."""
    if not expansions:
        return characters
    out: list[CharacterSlot2Report] = []
    for ch in characters:
        updated: list[Slot2Comparison] = []
        for cmp_ in ch.comparisons:
            if cmp_.recommended_id and cmp_.recommended_id in expansions:
                updated.append(
                    replace(
                        cmp_,
                        recommended_expansion=expansions[cmp_.recommended_id],
                    )
                )
            else:
                updated.append(cmp_)
        ch.comparisons = updated
        out.append(ch)
    return out


def build_export_bundle(
    input_paths: list[str | Path],
    *,
    profile: str | ProfileId = "dex",
    artisans_prize_owned: bool = False,
    include_anniversary: bool = False,
    persona_order: list[str] | None = None,
    socket_overrides: dict[int, tuple[str | None, str | None]] | None = None,
    type78_slot_by_parent_id: dict[int, int | None] | None = None,
    eqr_aug_html_by_id: dict[int, str] | None = None,
    fetch_eqr_augs: bool = True,
    chest_class_overrides: dict[int, tuple[str | None, str | None]] | None = None,
    fetch_chest_class: bool = True,
    fetch_expansions: bool = True,
    catalog_html: str | None = None,
    shield_catalog_html: str | None = None,
    session_weights: dict[str, float] | None = None,
    on_progress: ProgressFn | None = None,
) -> ExportBundle:
    """Parse inventories, fetch raidloot catalog(s), and compare Slot2 augs.

    ``input_paths`` may be files and/or folders. When files are listed explicitly,
    order is preserved (after de-dupe). ``persona_order`` reorders columns when set.

    Character class is taken from the inventory filename when present; otherwise
    from the equipped Chest item's Class line (raidloot / EQ Resource). Each
    character then uses the aug profile for that class (Dex / INT / WIS).

    ``on_progress`` receives ``{"message": str, "fraction": float}`` updates for
    stages through expansion resolve (fractions up to 0.95). File write progress
    is reported by the GUI worker.

    Test hooks: ``socket_overrides``, ``type78_slot_by_parent_id``,
    ``chest_class_overrides``, ``catalog_html``.
    """
    fallback_profile = normalize_profile(str(profile))
    warnings: list[str] = []

    p0, p1 = _PROGRESS_PARSE
    report_progress(on_progress, "Parsing inventories…", p0, p1, 0, 1)

    files: list[Path] = []
    for raw in input_paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(discover_inventory_files(path))
        elif path.is_file():
            files.append(path)

    seen: set[str] = set()
    unique_files: list[Path] = []
    for f in files:
        key = str(f.resolve())
        if key not in seen:
            seen.add(key)
            unique_files.append(f)

    roster = build_roster(unique_files, saved_order=persona_order)
    ordered_paths = [Path(e.path) for e in roster] if roster else unique_files

    inventories: list[InventoryData] = []
    for filepath in ordered_paths:
        data = parse_inventory_file(filepath)
        if data is None:
            warnings.append(f"Could not parse: {filepath}")
            continue
        inventories.append(data)

    report_progress(on_progress, "Parsing inventories…", p0, p1, 1, 1)

    explicit_by_path: dict[str, str | None] = {}
    for e in roster:
        explicit_by_path[str(Path(e.path))] = e.class_abbr

    c0, c1 = _PROGRESS_CLASSES
    report_progress(on_progress, "Resolving character classes…", c0, c1, 0, 1)
    class_by_path = resolve_classes_for_inventories(
        inventories,
        explicit_by_path=explicit_by_path,
        overrides=chest_class_overrides,
        allow_network=fetch_chest_class,
        on_progress=_range_item_progress(
            on_progress, "Resolving character classes…", c0, c1
        ),
    )
    report_progress(on_progress, "Resolving character classes…", c0, c1, 1, 1)

    # Apply detected classes onto inventory + roster for export metadata.
    enriched_roster: list[RosterEntry] = []
    path_to_roster = {str(Path(e.path)): e for e in roster}
    for data in inventories:
        path = str(Path(data.filepath))
        class_abbr = class_by_path.get(path)
        data.class_abbr = class_abbr
        old = path_to_roster.get(path)
        if old is not None:
            enriched_roster.append(
                RosterEntry(
                    persona_key=persona_key(old.character, old.server, class_abbr),
                    character=old.character,
                    server=old.server,
                    class_abbr=class_abbr,
                    path=old.path,
                )
            )
        else:
            enriched_roster.append(
                RosterEntry(
                    persona_key=persona_key(data.character, data.server, class_abbr),
                    character=data.character,
                    server=data.server,
                    class_abbr=class_abbr,
                    path=data.filepath,
                )
            )
    if enriched_roster:
        roster = enriched_roster

    parent_ids: list[int] = []
    for data in inventories:
        parent_ids.extend(collect_equipped_parent_ids(data))

    s0, s1 = _PROGRESS_SOCKETS
    if type78_slot_by_parent_id is None:
        report_progress(on_progress, "Resolving item sockets…", s0, s1, 0, 1)
        type78_slot_by_parent_id = resolve_type78_slots(
            parent_ids,
            overrides=socket_overrides,
            on_progress=_range_item_progress(
                on_progress, "Resolving item sockets…", s0, s1
            ),
        )
    report_progress(on_progress, "Resolving item sockets…", s0, s1, 1, 1)

    # Profile per character from class; fall back to GUI/default profile.
    char_profiles: list[ProfileId] = []
    for data in inventories:
        char_profiles.append(profile_from_class(data.class_abbr, fallback_profile))

    profile_counts = Counter(char_profiles)
    # Ranked reference / bundle label: majority auto profile, else fallback.
    if profile_counts:
        primary_profile = profile_counts.most_common(1)[0][0]
    else:
        primary_profile = fallback_profile

    catalogs: dict[ProfileId, CatalogResult] = {}

    def catalog_for(pid: ProfileId) -> CatalogResult:
        if pid not in catalogs:
            cat = fetch_catalog(
                pid,
                html_override=catalog_html,
                shield_html_override=shield_catalog_html,
            )
            if cat.warning:
                warnings.append(cat.warning)
            filtered = filter_anniversary_augs(
                cat.augs, include_anniversary=include_anniversary
            )
            catalogs[pid] = CatalogResult(
                profile=cat.profile,
                augs=filtered,
                fetched_at=cat.fetched_at,
                from_cache=cat.from_cache,
                url=cat.url,
                warning=cat.warning,
            )
        return catalogs[pid]

    cat0, cat1 = _PROGRESS_CATALOG
    profiles_needed = list(dict.fromkeys([primary_profile, *char_profiles]))
    n_profiles = len(profiles_needed)
    report_progress(
        on_progress, "Fetching raidloot catalog…", cat0, cat1, 0, max(n_profiles, 1)
    )
    for i, pid in enumerate(profiles_needed, start=1):
        catalog_for(pid)
        report_progress(
            on_progress,
            f"Fetching raidloot catalog… ({i}/{n_profiles})",
            cat0,
            cat1,
            i,
            n_profiles,
        )

    # Ensure primary catalog exists for ranked list / bundle.catalog.
    primary_catalog = catalog_for(primary_profile)

    characters: list[CharacterSlot2Report] = []
    servers: list[str] = []
    # Advanced GUI weights apply only to a single-character generate.
    active_session_weights = (
        session_weights if session_weights and len(inventories) == 1 else None
    )
    from eq_augs.weights import session_absolute_weights

    cmp0, cmp1 = _PROGRESS_COMPARE
    n_chars = len(inventories)
    report_progress(
        on_progress, "Comparing characters…", cmp0, cmp1, 0, max(n_chars, 1)
    )

    with session_absolute_weights(active_session_weights):
        for i, (data, char_profile) in enumerate(
            zip(inventories, char_profiles), start=1
        ):
            report = compare_character(
                data,
                catalog_for(char_profile),
                artisans_prize_owned=artisans_prize_owned,
                profile=char_profile,
                class_abbr=data.class_abbr,
                type78_slot_by_parent_id=type78_slot_by_parent_id,
                eqr_aug_html_by_id=eqr_aug_html_by_id,
                fetch_eqr_augs=fetch_eqr_augs,
            )
            characters.append(report)
            if data.server:
                servers.append(data.server)
            report_progress(
                on_progress,
                f"Comparing characters… ({i}/{n_chars})",
                cmp0,
                cmp1,
                i,
                max(n_chars, 1),
            )

        if active_session_weights:
            warnings.append(
                "Advanced weight overrides applied for this single-character report."
            )

        # Expansion names for recommended upgrade IDs (EQ Resource expac icon).
        rec_ids: list[int] = []
        for ch in characters:
            for cmp_ in ch.comparisons:
                if cmp_.status not in NEEDS_UPGRADE_STATUSES:
                    continue
                if cmp_.recommended_id and cmp_.recommended_id > 0:
                    rec_ids.append(cmp_.recommended_id)
        e0, e1 = _PROGRESS_EXPANSIONS
        report_progress(on_progress, "Resolving expansions…", e0, e1, 0, 1)
        expansions = resolve_item_expansions(
            rec_ids,
            html_overrides=eqr_aug_html_by_id,
            allow_network=fetch_expansions,
            on_progress=_range_item_progress(
                on_progress, "Resolving expansions…", e0, e1
            ),
        )
        characters = apply_expansions_to_characters(characters, expansions)
        report_progress(on_progress, "Resolving expansions…", e0, e1, 1, 1)

        # Ranked reference: top augs for every profile present on the roster,
        # ordered by weighted score for a representative class of that profile.
        from eq_augs.weights import rank_key

        _PROFILE_REP_CLASS = {"dex": "ROG", "int": "WIZ", "wis": "CLR"}

        profile_order = [p for p in ("dex", "int", "wis") if p in set(char_profiles)]
        if not profile_order:
            profile_order = [primary_profile]

        # Prefer a roster character's class when scoring their profile's ranked list.
        rep_class_for_profile: dict[ProfileId, str | None] = {}
        for data, char_profile in zip(inventories, char_profiles):
            if char_profile not in rep_class_for_profile and data.class_abbr:
                rep_class_for_profile[char_profile] = data.class_abbr.strip().upper()

        ranked: list[AugCandidate] = []
        for pid in profile_order:
            cat = catalog_for(pid)
            rep_class = rep_class_for_profile.get(pid) or _PROFILE_REP_CLASS.get(pid)
            scored = [
                a
                for a in cat.augs
                if not a.shield_only
                and (artisans_prize_owned or a.item_id != 88785)
            ]
            scored.sort(
                key=lambda a: rank_key(a, rep_class, "Head", profile=pid)
            )
            ranked.extend(scored[:50])

    distinct_servers = {s for s in servers if s}
    server = ""
    if len(distinct_servers) == 1:
        server = next(iter(distinct_servers))
    elif distinct_servers:
        server = "Team"

    prefix = export_prefix_from_roster(roster) if roster else (server or "Team")
    show_server = len(distinct_servers) > 1
    farm_list = build_farm_list(characters, roster)

    return ExportBundle(
        profile=primary_profile,
        profile_label=PROFILE_LABELS[primary_profile],
        artisans_prize_owned=artisans_prize_owned,
        catalog=primary_catalog,
        characters=characters,
        ranked_augs=ranked,
        farm_list=farm_list,
        warnings=warnings,
        server=server or prefix,
        export_prefix=prefix,
        show_server_in_columns=show_server,
        roster=roster,
        include_anniversary=include_anniversary,
    )


def default_profile_from_paths(
    input_paths: list[str | Path],
    *,
    fetch_chest_class: bool = True,
    chest_class_overrides: dict[int, tuple[str | None, str | None]] | None = None,
) -> ProfileId:
    """Infer aug profile from filename class or equipped Chest armor class."""
    inventories: list[InventoryData] = []
    for raw in input_paths:
        path = Path(raw)
        candidates = discover_inventory_files(path) if path.is_dir() else [path]
        for f in candidates:
            data = parse_inventory_file(f)
            if data:
                inventories.append(data)

    if not inventories:
        return "dex"

    class_by_path = resolve_classes_for_inventories(
        inventories,
        overrides=chest_class_overrides,
        allow_network=fetch_chest_class,
    )
    profiles: list[ProfileId] = []
    for data in inventories:
        path = str(Path(data.filepath))
        class_abbr = class_by_path.get(path) or data.class_abbr
        inferred = profile_for_class(class_abbr)
        if inferred:
            profiles.append(inferred)

    if not profiles:
        return "dex"
    return Counter(profiles).most_common(1)[0][0]
