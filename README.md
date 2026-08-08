# EQ Augs

EverQuest **Slot2 type 7/8** aug checker: compare inventory dumps against live
[raidloot.com](https://www.raidloot.com) rankings, with Charm/Range/Feet awareness,
ownership / need-to-farm tracking, and optional anniversary gems.

**Version:** 0.3.0

## Features

- Parse `*-Inventory.txt` dumps for equipped type 7/8 augs (socket map via raidloot / EQ Resource).
- Class (and Dex / INT / WIS catalog) from filename or **equipped Chest** armor.
- BiS loadout with **priority holes first** (Range → Charm → Feet when high-AC
  applies), Lore uniqueness, and cross-slot **moves**. General slots share a pool —
  best owned/farmable set equipped, no general↔general reshuffle.
- **Artisan's Prize** Ear BiS when marked owned.
- **Include Anniversary** — optional; names containing `Gem of Distant Echoes` are excluded by default.
- **Owned / Need to farm** — recommendations checked against the full inventory dump
  (bags, bank, equipped); moves from priority slots (and pieces they free) count as owned.
- Item links and expansion names from **EQ Resource** (`items.eqresource.com`).
- Excel + HTML reports (upgrade table, Need to Farm sheet/section, ranked reference).

## Quick start

```bat
run_gui.bat
```

Or CLI:

```bat
py -m eq_augs path\to\InventoryDumps --format both
py -m eq_augs path\to\file-Inventory.txt --artisans-prize --include-anniversary
```

One-file Windows build:

```bat
build_exe.bat
```

Output: `dist\EQAugs-0.3.0.exe`

## Aug options (GUI)

| Option | Default | Meaning |
|--------|---------|---------|
| I own Artisan's Prize | off | Ear recommends Artisan's Prize when appropriate |
| Include Anniversary augs | off | Include `Gem of Distant Echoes` anniversary gems |

Stat profile is **not** chosen in the UI; it is detected from Chest class (or filename class).

## Reports

- **Augs** — current Slot2 vs recommended upgrade; Owned / Move from / Need to farm; expansion.
- **Need to Farm** — recommended upgrades missing from inventory (not bag/bank/equipped).
- **Ranked Augs** — catalog reference list for roster profiles.
- Item names link to EQ Resource item pages.

## Caches (`%LOCALAPPDATA%\EQ Augs\`)

| File | Purpose |
|------|---------|
| `raidloot_cache.json` | Profile catalogs + shield augs |
| `item_sockets_cache.json` | Parent item → type 7/8 dump slot |
| `item_class_cache.json` | Chest item → class |
| `eqresource_aug_cache.json` | Stats for equipped augs missing from raidloot |
| `eqresource_expansion_cache.json` | Expansion names for recommended item IDs |
| `settings.json` | Roster column order |
| `weight_overrides.json` | Optional scoring overrides |

## Development

```bat
py -m pip install -e ".[dev]"
py -m pytest
```

Weighted scoring tables: `src/eq_augs/data/weights/`. Regenerated human-readable dump:

```bat
py scripts/print_weights_doc.py
```

→ `Example/Aug_Selection_Weights.txt`

Merge plan into Inventory Parser: see [MERGE_NOTES.md](MERGE_NOTES.md).
