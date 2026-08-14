"""Character roster discovery, selection keys, and saved column order."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TypeVar

from eq_augs.parser import discover_inventory_files, parse_inventory_filename

T = TypeVar("T")


@dataclass(frozen=True)
class RosterEntry:
    """One character column in the GUI roster / export."""

    persona_key: str
    character: str
    server: str
    class_abbr: str | None
    path: str

    @property
    def display_name(self) -> str:
        return format_character_display_name(self.character, self.class_abbr)


@dataclass(frozen=True)
class FolderCharacterChoice:
    """Inventory dumps for one character+server discovered in a folder.

    Class-tagged files (``Name_server-CLASS-Inventory.txt``) are all kept.
    A generic ``Name_server-Inventory.txt`` is dropped when any class-tagged
    dump exists for the same character, matching Inventory Parser.
    """

    character: str
    server: str
    class_abbr: str | None
    path: str
    inventory_paths: tuple[str, ...] = ()
    class_abbrs: tuple[str, ...] = ()

    @property
    def persona_key(self) -> str:
        if len(self.class_abbrs) == 1:
            return persona_key(self.character, self.server, self.class_abbrs[0])
        return persona_key(self.character, self.server)

    @property
    def paths(self) -> list[str]:
        if self.inventory_paths:
            return list(self.inventory_paths)
        return [self.path] if self.path else []

    @property
    def display_name(self) -> str:
        return format_character_display_name(self.character, self.class_abbrs)

    @property
    def summary(self) -> str:
        n = len(self.paths)
        if n == 1:
            return "1 inventory"
        return f"{n} inventory"


def format_character_display_name(
    character: str,
    class_abbr: str | None | tuple[str, ...] | list[str] = None,
) -> str:
    """Format a label like ``Deflub ( PAL )`` or ``Deflub ( PAL, WAR )``."""
    abbrs: list[str] = []
    if isinstance(class_abbr, (list, tuple)):
        abbrs = [str(a).strip().upper() for a in class_abbr if a]
    elif class_abbr:
        abbrs = [str(class_abbr).strip().upper()]
    if len(abbrs) == 1:
        return f"{character} ( {abbrs[0]} )"
    if len(abbrs) > 1:
        return f"{character} ( {', '.join(abbrs)} )"
    return character


def persona_key(character: str, server: str, class_abbr: str | None = None) -> str:
    """Stable key for a character (optionally class-specific), matching Inventory Parser."""
    base = f"{character}_{server}"
    if class_abbr:
        return f"{base}_{class_abbr.upper()}"
    return base


def _char_server_key(character: str, server: str) -> str:
    return f"{character.casefold()}\0{server.casefold()}"


def superseded_generic_inventory_keys(inventory_paths: list[str | Path]) -> set[str]:
    """Char+server keys that have at least one class-tagged inventory among inputs."""
    keys: set[str] = set()
    for raw in inventory_paths:
        character, server, class_abbr = parse_inventory_filename(raw)
        if class_abbr:
            keys.add(_char_server_key(character, server))
    return keys


def filter_inventories_for_bindings(inventory_paths: list[str | Path]) -> list[Path]:
    """Drop generic inventories when class-tagged dumps exist for the same character."""
    resolved = [Path(p) for p in inventory_paths]
    superseded = superseded_generic_inventory_keys(resolved)
    if not superseded:
        return resolved
    filtered: list[Path] = []
    for raw in resolved:
        character, server, class_abbr = parse_inventory_filename(raw)
        if class_abbr is None and _char_server_key(character, server) in superseded:
            continue
        filtered.append(raw)
    return filtered


def settings_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".local" / "share"
    return base / "EQ Augs" / "settings.json"


def load_settings() -> dict:
    path = settings_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_settings(settings: dict) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def save_character_column_order(order: list[str]) -> None:
    settings = load_settings()
    settings["character_column_order"] = order
    _save_settings(settings)


def saved_character_column_order() -> list[str]:
    raw = load_settings().get("character_column_order", [])
    if not isinstance(raw, list):
        return []
    return [str(key) for key in raw if key]


def order_by_persona_keys(items: list[T], order: list[str], *, key_fn) -> list[T]:
    by_key = {key_fn(item): item for item in items}
    ordered: list[T] = []
    seen: set[str] = set()
    for key in order:
        item = by_key.get(key)
        if item is not None and key not in seen:
            ordered.append(item)
            seen.add(key)
    for item in items:
        key = key_fn(item)
        if key not in seen:
            ordered.append(item)
            seen.add(key)
    return ordered


def _class_abbrs_from_inventory_paths(inventory_paths: list[Path] | tuple[Path, ...]) -> tuple[str, ...]:
    classes: list[str] = []
    seen: set[str] = set()
    for inv_path in inventory_paths:
        _character, _server, class_abbr = parse_inventory_filename(inv_path)
        if not class_abbr or class_abbr in seen:
            continue
        seen.add(class_abbr)
        classes.append(class_abbr)
    return tuple(classes)


def discover_folder_character_choices(folder: str | Path) -> list[FolderCharacterChoice]:
    """Group inventory dumps in a folder by character+server for GUI selection.

    Keeps every class-tagged dump. When any class-tagged file exists for a
    character, the generic ``Name_server-Inventory.txt`` is ignored.
    """
    files = filter_inventories_for_bindings(discover_inventory_files(folder))
    inventory_lists: dict[tuple[str, str], list[Path]] = {}
    names: dict[tuple[str, str], tuple[str, str]] = {}
    for path in files:
        character, server, _class_abbr = parse_inventory_filename(path)
        key = (character.casefold(), server.casefold())
        names[key] = (character, server)
        inventory_lists.setdefault(key, []).append(path.resolve())

    choices: list[FolderCharacterChoice] = []
    for key, (character, server) in names.items():
        inv_paths = tuple(
            sorted(set(inventory_lists[key]), key=lambda p: p.name.casefold())
        )
        class_abbrs = _class_abbrs_from_inventory_paths(inv_paths)
        str_paths = tuple(str(p) for p in inv_paths)
        choices.append(
            FolderCharacterChoice(
                character=character,
                server=server,
                class_abbr=class_abbrs[0] if class_abbrs else None,
                path=str_paths[0] if str_paths else "",
                inventory_paths=str_paths,
                class_abbrs=class_abbrs,
            )
        )
    return sorted(choices, key=lambda c: (c.character.casefold(), c.server.casefold()))


def unique_servers(choices: list[FolderCharacterChoice] | list[RosterEntry]) -> list[str]:
    seen: dict[str, str] = {}
    for c in choices:
        if c.server:
            seen[c.server.casefold()] = c.server
    return sorted(seen.values(), key=str.casefold)


def build_roster(
    file_paths: list[str | Path],
    saved_order: list[str] | None = None,
    *,
    detect_chest_class: bool = False,
    chest_class_overrides: dict[int, tuple[str | None, str | None]] | None = None,
    fetch_chest_class: bool = True,
) -> list[RosterEntry]:
    """Build roster entries from inventory paths, applying saved column order.

    When ``detect_chest_class`` is True, missing filename classes are filled from
    the equipped Chest item's Class line (raidloot / EQ Resource).
    """
    entries: list[RosterEntry] = []
    seen_keys: set[str] = set()
    for path in filter_inventories_for_bindings(file_paths):
        if not path.is_file():
            continue
        character, server, class_abbr = parse_inventory_filename(path)
        key = persona_key(character, server, class_abbr)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        entries.append(
            RosterEntry(
                persona_key=key,
                character=character,
                server=server,
                class_abbr=class_abbr,
                path=str(path.resolve()),
            )
        )
    ordered = order_by_persona_keys(
        entries,
        saved_order or saved_character_column_order(),
        key_fn=lambda e: e.persona_key,
    )
    if detect_chest_class:
        ordered = enrich_roster_classes(
            ordered,
            overrides=chest_class_overrides,
            allow_network=fetch_chest_class,
        )
    return ordered


def enrich_roster_classes(
    entries: list[RosterEntry],
    *,
    overrides: dict[int, tuple[str | None, str | None]] | None = None,
    allow_network: bool = True,
) -> list[RosterEntry]:
    """Fill missing class abbrs from equipped Chest armor; refresh persona keys."""
    from eq_augs.chest_class import resolve_classes_for_inventories
    from eq_augs.parser import parse_inventory_file

    inventories = []
    for e in entries:
        data = parse_inventory_file(e.path)
        if data is not None:
            inventories.append(data)
    if not inventories:
        return list(entries)

    explicit = {str(Path(e.path)): e.class_abbr for e in entries}
    class_by_path = resolve_classes_for_inventories(
        inventories,
        explicit_by_path=explicit,
        overrides=overrides,
        allow_network=allow_network,
    )
    enriched: list[RosterEntry] = []
    for e in entries:
        path = str(Path(e.path))
        class_abbr = class_by_path.get(path) or e.class_abbr
        if class_abbr:
            class_abbr = class_abbr.strip().upper()
        enriched.append(
            RosterEntry(
                persona_key=persona_key(e.character, e.server, class_abbr),
                character=e.character,
                server=e.server,
                class_abbr=class_abbr,
                path=e.path,
            )
        )
    return enriched


def enrich_folder_choice_classes(
    choices: list[FolderCharacterChoice],
    *,
    overrides: dict[int, tuple[str | None, str | None]] | None = None,
    allow_network: bool = True,
) -> list[FolderCharacterChoice]:
    """Fill missing picker class badges from equipped Chest armor."""
    from eq_augs.chest_class import resolve_classes_for_inventories
    from eq_augs.parser import parse_inventory_file

    need = []
    for choice in choices:
        if choice.class_abbrs:
            continue
        for raw in choice.paths:
            data = parse_inventory_file(raw)
            if data is not None:
                need.append(data)
    if not need:
        return list(choices)

    class_by_path = resolve_classes_for_inventories(
        need,
        overrides=overrides,
        allow_network=allow_network,
    )
    enriched: list[FolderCharacterChoice] = []
    for choice in choices:
        if choice.class_abbrs:
            enriched.append(choice)
            continue
        abbrs: list[str] = []
        seen: set[str] = set()
        for raw in choice.paths:
            abbr = class_by_path.get(str(Path(raw)))
            if not abbr:
                continue
            key = abbr.strip().upper()
            if key in seen:
                continue
            seen.add(key)
            abbrs.append(key)
        first = abbrs[0] if abbrs else choice.class_abbr
        enriched.append(
            replace(
                choice,
                class_abbr=first,
                class_abbrs=tuple(abbrs),
            )
        )
    return enriched


def paths_for_removal(
    removing_keys: list[str],
    roster: list[RosterEntry],
) -> list[str]:
    """Return inventory paths belonging to personas being removed."""
    drop = {k.casefold() for k in removing_keys}
    return [e.path for e in roster if e.persona_key.casefold() in drop or e.persona_key in removing_keys]


def export_prefix_from_roster(roster: list[RosterEntry]) -> str:
    """
    Filename prefix: single character name, else shared server, else Team.
    Mirrors Inventory Parser default_export_prefix behavior (without display-name map).
    """
    if len(roster) == 1:
        return roster[0].character or "Team"
    servers = {e.server for e in roster if e.server}
    if len(servers) == 1:
        return next(iter(servers))
    return "Team"


def column_label(entry: RosterEntry, *, show_server: bool) -> str:
    if show_server and entry.server:
        return f"{entry.character} ({entry.server})"
    return entry.character
