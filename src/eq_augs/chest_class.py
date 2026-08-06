"""Detect character class from equipped Chest armor (raidloot / EQ Resource)."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from eq_augs.parser import InventoryData, InventoryItem
from eq_augs.profiles import CLASS_TO_PROFILE, ProfileId, profile_for_class

USER_AGENT = "EQ-Augs/0.2 (Slot2 type 7/8 checker; local tool)"
CACHE_FILENAME = "item_class_cache.json"
RAIDLOOT_ITEM_URL = "https://www.raidloot.com/items?name={item_id}"
EQRESOURCE_ITEM_URL = "https://items.eqresource.com/items.php?id={item_id}"

# Full names and abbreviations → canonical EQ class abbr.
_CLASS_ALIASES: dict[str, str] = {
    "war": "WAR",
    "warrior": "WAR",
    "pal": "PAL",
    "paladin": "PAL",
    "shd": "SHD",
    "sk": "SHD",
    "shadowknight": "SHD",
    "shadow knight": "SHD",
    "mnk": "MNK",
    "monk": "MNK",
    "rng": "RNG",
    "ranger": "RNG",
    "rog": "ROG",
    "rogue": "ROG",
    "bst": "BST",
    "beastlord": "BST",
    "brd": "BRD",
    "bard": "BRD",
    "ber": "BER",
    "berserker": "BER",
    "enc": "ENC",
    "enchanter": "ENC",
    "wiz": "WIZ",
    "wizard": "WIZ",
    "mag": "MAG",
    "magician": "MAG",
    "nec": "NEC",
    "necromancer": "NEC",
    "shm": "SHM",
    "shaman": "SHM",
    "clr": "CLR",
    "cleric": "CLR",
    "dru": "DRU",
    "druid": "DRU",
}

_RAIDLOOT_CLASS_RE = re.compile(
    r"<label>\s*Class:\s*</label>\s*(.*?)(?=<label>|<br\s*/?>|$)",
    re.IGNORECASE | re.DOTALL,
)
_EQR_CLASS_RE = re.compile(r"Class:\s*([^<\n]+)", re.IGNORECASE)
_TOKEN_SPLIT_RE = re.compile(r"[,/]| and |\s+")


def cache_path() -> Path:
    local = os.environ.get("LOCALAPPDATA") or os.environ.get("HOME") or "."
    root = Path(local) / "EQ Augs"
    root.mkdir(parents=True, exist_ok=True)
    return root / CACHE_FILENAME


def _http_get(url: str, timeout: float = 30.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _load_cache() -> dict:
    path = cache_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(data: dict) -> None:
    cache_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _html_to_text(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", text).strip()


def normalize_class_token(token: str) -> str | None:
    """Map a class name/abbr token to WAR/ROG/… or None if not a real class."""
    key = re.sub(r"\s+", " ", (token or "").strip()).casefold()
    if not key or key == "all":
        return None
    return _CLASS_ALIASES.get(key)


def parse_class_list(text: str) -> list[str]:
    """Parse 'ROG' / 'Rogue' / 'WAR PAL SHD' into unique canonical abbrs."""
    cleaned = _html_to_text(text)
    if not cleaned:
        return []
    # Prefer multi-word aliases before splitting hard.
    lower = cleaned.casefold()
    found: list[str] = []
    seen: set[str] = set()
    # Try longest alias phrases first.
    for alias, abbr in sorted(_CLASS_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if " " in alias and alias in lower:
            if abbr not in seen:
                found.append(abbr)
                seen.add(abbr)
    for part in _TOKEN_SPLIT_RE.split(cleaned):
        abbr = normalize_class_token(part)
        if abbr and abbr not in seen:
            found.append(abbr)
            seen.add(abbr)
    return found


def parse_raidloot_item_classes(html: str) -> list[str]:
    m = _RAIDLOOT_CLASS_RE.search(html or "")
    if not m:
        # Plain-text fallback
        m2 = re.search(r"Class:\s*([A-Za-z][A-Za-z /,]*)", html or "", re.IGNORECASE)
        return parse_class_list(m2.group(1)) if m2 else []
    return parse_class_list(m.group(1))


def parse_eqresource_item_classes(html: str) -> list[str]:
    m = _EQR_CLASS_RE.search(html or "")
    if not m:
        return []
    return parse_class_list(m.group(1))


def equipped_chest_item(data: InventoryData) -> InventoryItem | None:
    """Return the equipped Chest parent item, if any."""
    for item in data.items:
        if item.location != "Chest":
            continue
        if item.item_id <= 0:
            continue
        if item.name.casefold() == "empty":
            continue
        return item
    return None


def fetch_item_classes(
    item_id: int,
    *,
    force_refresh: bool = False,
    raidloot_html: str | None = None,
    eqr_html: str | None = None,
    skip_cache_write: bool = False,
) -> list[str]:
    """
    Resolve usable class list for an item id (Chest armor).

    Prefers raidloot abbreviations; falls back to EQ Resource names.
    """
    if item_id <= 0:
        return []

    if raidloot_html is not None or eqr_html is not None:
        classes = parse_raidloot_item_classes(raidloot_html or "")
        if not classes:
            classes = parse_eqresource_item_classes(eqr_html or "")
        return classes

    cache = _load_cache()
    key = str(item_id)
    if not force_refresh and key in cache and "classes" in cache[key]:
        raw = cache[key].get("classes") or []
        return [str(c).upper() for c in raw if str(c).upper() in CLASS_TO_PROFILE]

    classes: list[str] = []
    try:
        html = _http_get(RAIDLOOT_ITEM_URL.format(item_id=item_id))
        classes = parse_raidloot_item_classes(html)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        classes = []

    if not classes:
        try:
            eqr = _http_get(EQRESOURCE_ITEM_URL.format(item_id=item_id))
            classes = parse_eqresource_item_classes(eqr)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            classes = []

    if not skip_cache_write:
        cache[key] = {
            "classes": classes,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_cache(cache)
    return classes


def primary_class_from_list(classes: list[str]) -> str | None:
    """Pick a single class abbr when the item lists one (or more) classes."""
    usable = [c for c in classes if c in CLASS_TO_PROFILE]
    if not usable:
        return None
    # Single-class armor is the common Chest case.
    if len(usable) == 1:
        return usable[0]
    # Multi-class: prefer first listed (raidloot / EQR order).
    return usable[0]


def detect_class_from_chest(
    data: InventoryData,
    *,
    force_refresh: bool = False,
    overrides: dict[int, tuple[str | None, str | None]] | None = None,
    allow_network: bool = True,
) -> str | None:
    """
    Detect character class from equipped Chest armor.

    Returns a canonical abbr (e.g. ``ROG``) or None.
    """
    chest = equipped_chest_item(data)
    if chest is None:
        return None
    overrides = overrides or {}
    ov = overrides.get(chest.item_id)
    if ov is not None:
        classes = fetch_item_classes(
            chest.item_id,
            raidloot_html=ov[0],
            eqr_html=ov[1],
        )
    elif allow_network:
        classes = fetch_item_classes(chest.item_id, force_refresh=force_refresh)
    else:
        return None
    return primary_class_from_list(classes)


def resolve_character_class(
    data: InventoryData,
    *,
    explicit_class: str | None = None,
    force_refresh: bool = False,
    overrides: dict[int, tuple[str | None, str | None]] | None = None,
    allow_network: bool = True,
) -> str | None:
    """
    Prefer filename/roster class; otherwise look up Chest armor class.
    """
    if explicit_class:
        abbr = explicit_class.strip().upper()
        if abbr in CLASS_TO_PROFILE:
            return abbr
    if data.class_abbr:
        abbr = data.class_abbr.strip().upper()
        if abbr in CLASS_TO_PROFILE:
            return abbr
    return detect_class_from_chest(
        data,
        force_refresh=force_refresh,
        overrides=overrides,
        allow_network=allow_network,
    )


def profile_from_class(class_abbr: str | None, fallback: ProfileId = "dex") -> ProfileId:
    return profile_for_class(class_abbr) or fallback


def resolve_classes_for_inventories(
    inventories: Iterable[InventoryData],
    *,
    explicit_by_path: dict[str, str | None] | None = None,
    overrides: dict[int, tuple[str | None, str | None]] | None = None,
    allow_network: bool = True,
    polite_delay_s: float = 0.05,
) -> dict[str, str | None]:
    """
    Map inventory filepath → class abbr.

    Batches unique Chest item ids so each armor is fetched once.
    """
    explicit_by_path = {
        str(Path(k)): (v.strip().upper() if v else None)
        for k, v in (explicit_by_path or {}).items()
    }
    overrides = overrides or {}
    result: dict[str, str | None] = {}

    need_fetch: dict[int, list[str]] = {}

    for data in inventories:
        path = str(Path(data.filepath))
        chosen: str | None = None
        for candidate in (explicit_by_path.get(path), data.class_abbr):
            if candidate and candidate.strip().upper() in CLASS_TO_PROFILE:
                chosen = candidate.strip().upper()
                break
        if chosen:
            result[path] = chosen
            continue

        chest = equipped_chest_item(data)
        if chest is None:
            result[path] = None
            continue
        need_fetch.setdefault(chest.item_id, []).append(path)

    fetched_live = 0
    class_by_item: dict[int, str | None] = {}
    for item_id in sorted(need_fetch):
        ov = overrides.get(item_id)
        if ov is not None:
            classes = fetch_item_classes(
                item_id, raidloot_html=ov[0], eqr_html=ov[1]
            )
        elif allow_network:
            if fetched_live > 0 and polite_delay_s > 0:
                time.sleep(polite_delay_s)
            classes = fetch_item_classes(item_id)
            fetched_live += 1
        else:
            classes = []
        class_by_item[item_id] = primary_class_from_list(classes)

    for item_id, paths in need_fetch.items():
        abbr = class_by_item.get(item_id)
        for path in paths:
            result[path] = abbr

    return result
