"""Look up parent-item augment socket types (raidloot / EQ Resource) for type 7/8 holes."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

USER_AGENT = "EQ-Augs/0.2 (Slot2 type 7/8 checker; local tool)"
CACHE_FILENAME = "item_sockets_cache.json"

RAIDLOOT_ITEM_URL = "https://www.raidloot.com/items?name={item_id}"
EQRESOURCE_ITEM_URL = "https://items.eqresource.com/items.php?id={item_id}"

_TYPE78 = frozenset({7, 8})

_RAIDLOOT_SLOT_RE = re.compile(
    r"Slot\s+(\d+)\s*,\s*type\s+(\d+)",
    re.IGNORECASE,
)
_EQR_SLOT_RE = re.compile(
    r"getAugs\s*\(\s*['\"](\d+)['\"]\s*,\s*['\"]\d+['\"]\s*,\s*['\"](\d+)['\"]\s*\)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AugSocket:
    slot: int
    aug_type: int


@dataclass
class ItemSocketMap:
    item_id: int
    sockets: list[AugSocket] = field(default_factory=list)
    source: str = ""
    fetched_at: str = ""
    from_cache: bool = False


def cache_path() -> Path:
    local = os.environ.get("LOCALAPPDATA") or os.environ.get("HOME") or "."
    root = Path(local) / "EQ Augs"
    root.mkdir(parents=True, exist_ok=True)
    return root / CACHE_FILENAME


def type78_dump_slot(sockets: Iterable[AugSocket]) -> int | None:
    """Lowest dump SlotN whose aug type is 7 or 8."""
    matches = [s.slot for s in sockets if s.aug_type in _TYPE78]
    return min(matches) if matches else None


def parse_raidloot_item_html(html: str, item_id: int | None = None) -> list[AugSocket]:
    """Parse ``Slot N, type T`` labels from a raidloot item page."""
    del item_id  # reserved for future scoped parsing
    by_slot: dict[int, int] = {}
    for m in _RAIDLOOT_SLOT_RE.finditer(html):
        slot = int(m.group(1))
        aug_type = int(m.group(2))
        by_slot[slot] = aug_type
    return [AugSocket(slot=s, aug_type=t) for s, t in sorted(by_slot.items())]


def parse_eqresource_item_html(html: str) -> list[AugSocket]:
    """Parse ``getAugs('type','id','slot')`` hooks from an EQ Resource item page."""
    by_slot: dict[int, int] = {}
    for m in _EQR_SLOT_RE.finditer(html):
        aug_type = int(m.group(1))
        slot = int(m.group(2))
        by_slot[slot] = aug_type
    return [AugSocket(slot=s, aug_type=t) for s, t in sorted(by_slot.items())]


def _http_get(url: str, timeout: float = 30.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def _load_cache() -> dict:
    path = cache_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(data: dict) -> None:
    path = cache_path()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _map_from_cache_entry(item_id: int, entry: dict) -> ItemSocketMap:
    sockets = [
        AugSocket(slot=int(s["slot"]), aug_type=int(s["type"]))
        for s in entry.get("sockets", [])
    ]
    return ItemSocketMap(
        item_id=item_id,
        sockets=sockets,
        source=str(entry.get("source", "cache")),
        fetched_at=str(entry.get("fetched_at", "")),
        from_cache=True,
    )


def _cache_entry(sock_map: ItemSocketMap) -> dict:
    return {
        "sockets": [{"slot": s.slot, "type": s.aug_type} for s in sock_map.sockets],
        "source": sock_map.source,
        "fetched_at": sock_map.fetched_at,
    }


def fetch_item_sockets(
    item_id: int,
    *,
    force_refresh: bool = False,
    html_override: str | None = None,
    eqr_html_override: str | None = None,
    skip_cache_write: bool = False,
) -> ItemSocketMap:
    """
    Fetch (or load cached) augment socket map for a parent gear item.

    ``html_override`` / ``eqr_html_override`` skip network (tests).
    """
    now = datetime.now(timezone.utc).isoformat()
    cache = _load_cache()
    key = str(item_id)

    if html_override is not None or eqr_html_override is not None:
        sockets: list[AugSocket] = []
        source = ""
        if html_override is not None:
            sockets = parse_raidloot_item_html(html_override, item_id)
            source = "raidloot"
        if not sockets and eqr_html_override is not None:
            sockets = parse_eqresource_item_html(eqr_html_override)
            source = "eqresource"
        return ItemSocketMap(
            item_id=item_id,
            sockets=sockets,
            source=source or "override",
            fetched_at=now,
            from_cache=False,
        )

    if not force_refresh and key in cache and cache[key].get("sockets") is not None:
        return _map_from_cache_entry(item_id, cache[key])

    sockets = []
    source = ""
    try:
        html = _http_get(RAIDLOOT_ITEM_URL.format(item_id=item_id))
        sockets = parse_raidloot_item_html(html, item_id)
        if sockets:
            source = "raidloot"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        sockets = []

    if not sockets:
        try:
            eqr_html = _http_get(EQRESOURCE_ITEM_URL.format(item_id=item_id))
            sockets = parse_eqresource_item_html(eqr_html)
            if sockets:
                source = "eqresource"
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            sockets = []

    sock_map = ItemSocketMap(
        item_id=item_id,
        sockets=sockets,
        source=source or "miss",
        fetched_at=now,
        from_cache=False,
    )
    if not skip_cache_write:
        # Cache misses too so we do not hammer the network every run.
        cache[key] = _cache_entry(sock_map)
        _save_cache(cache)
    return sock_map


def resolve_type78_slots(
    item_ids: Iterable[int],
    *,
    force_refresh: bool = False,
    overrides: dict[int, tuple[str | None, str | None]] | None = None,
    polite_delay_s: float = 0.05,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict[int, int | None]:
    """
    Map parent item IDs → dump SlotN for the first type 7/8 hole.

    Values are ``None`` when no type 7/8 socket was found.
    ``overrides`` maps item_id → (raidloot_html, eqr_html) for tests.
    ``on_progress(done, total)`` is called after each item (1-based done).
    """
    result: dict[int, int | None] = {}
    unique = sorted({int(i) for i in item_ids if int(i) > 0})
    overrides = overrides or {}
    fetched_live = 0
    total = len(unique)

    if total == 0 and on_progress is not None:
        on_progress(0, 0)

    for i, item_id in enumerate(unique, start=1):
        ov = overrides.get(item_id)
        if ov is not None:
            sock_map = fetch_item_sockets(
                item_id,
                html_override=ov[0],
                eqr_html_override=ov[1],
            )
        else:
            if fetched_live > 0 and polite_delay_s > 0:
                time.sleep(polite_delay_s)
            sock_map = fetch_item_sockets(item_id, force_refresh=force_refresh)
            if not sock_map.from_cache:
                fetched_live += 1
        result[item_id] = type78_dump_slot(sock_map.sockets)
        if on_progress is not None:
            on_progress(i, total)

    return result
