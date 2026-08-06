"""Character roster discovery, selection keys, and saved column order."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
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
        return self.character


@dataclass(frozen=True)
class FolderCharacterChoice:
    """One character found in a folder (may have one inventory dump)."""

    character: str
    server: str
    class_abbr: str | None
    path: str

    @property
    def persona_key(self) -> str:
        return persona_key(self.character, self.server, self.class_abbr)

    @property
    def summary(self) -> str:
        return "1 inventory"


def persona_key(character: str, server: str, class_abbr: str | None = None) -> str:
    """Stable key for a character (optionally class-specific), matching Inventory Parser."""
    base = f"{character}_{server}"
    if class_abbr:
        return f"{base}_{class_abbr.upper()}"
    return base


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


def discover_folder_character_choices(folder: str | Path) -> list[FolderCharacterChoice]:
    """Group inventory dumps in a folder by character+server for GUI selection."""
    files = discover_inventory_files(folder)
    by_key: dict[tuple[str, str], FolderCharacterChoice] = {}
    for path in files:
        character, server, class_abbr = parse_inventory_filename(path)
        key = (character.casefold(), server.casefold())
        # Prefer first file; if class-specific dump appears later, keep first unless
        # we have no entry yet.
        if key in by_key:
            continue
        by_key[key] = FolderCharacterChoice(
            character=character,
            server=server,
            class_abbr=class_abbr,
            path=str(path.resolve()),
        )
    return sorted(
        by_key.values(),
        key=lambda c: (c.character.casefold(), c.server.casefold()),
    )


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
    for raw in file_paths:
        path = Path(raw)
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
