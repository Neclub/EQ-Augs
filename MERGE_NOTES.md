# MERGE_NOTES — EQ Augs → Inventory Parser

This document describes how to merge the **EQ Augs** (Slot2 type 7/8 checker) into
[Inventory Parser](https://github.com/Neclub/Inventory-Parser) later.

**Standalone version:** `0.3.7`

## Purpose of this app

- Parse EverQuest `*-Inventory.txt` dumps for **equipped type 7/8** augs (usually Slot2;
  socket map may use another dump SlotN).
- Live-fetch ranked type 7/8 candidates from raidloot.com (Dex / INT / WIS filters).
- Recommend BiS per gear slot with **Charm/Range** (and **Feet** when high-AC)
  priority holes; **Primary/Secondary weapons ignored**; **shield Secondary** uses
  Shield Only augs. General slots share the best owned/farmable set.
- Special-case **Artisan's Prize** (item id `88785`, Ear-only) via an ownership checkbox.
- Optional **anniversary** filter: exclude `Gem of Distant Echoes` names unless enabled.
- Track **owned** recommendations (full dump) and a **Need to farm** list; EQ Resource
  item links + expansion names.
- Export Excel + HTML using the same architecture as Inventory Parser.

## Package map (current → future IP module)

| EQ Augs module | Suggested Inventory Parser location | Notes |
|----------------|-------------------------------------|-------|
| `eq_augs.parser` | Extend `inventory_parser.parser` | Add `extract_slot2_augs`, `collect_owned_item_ids`; keep IP's `extract_equipped_items` (skips `-Slot*`) unchanged |
| `eq_augs.slots` | Reuse `inventory_parser.slots` | `EQUIPMENT_SLOT_BASES`, `REPORT_SLOTS` ≡ `TEAM_GEAR_SLOTS`; bring `priority_aug_slots` / `aug_assignment_order` |
| `eq_augs.profiles` | `inventory_parser.slot2_augs.profiles` | New; class→Dex/INT/WIS map |
| `eq_augs.anniversary` | `inventory_parser.slot2_augs.anniversary` | New; Distant Echoes gem filter |
| `eq_augs.raidloot` | `inventory_parser.slot2_augs.raidloot` | New; fetch/cache/parse |
| `eq_augs.eqresource_augs` | `inventory_parser.slot2_augs.eqresource_augs` | New; catalog-miss stats + expansion cache |
| `eq_augs.item_sockets` | `inventory_parser.slot2_augs.item_sockets` | New; parent ID → type 7/8 dump SlotN |
| `eq_augs.chest_class` | `inventory_parser.slot2_augs.chest_class` | New; Chest armor → character class |
| `eq_augs.compare` | `inventory_parser.slot2_augs.compare` | New; loadout + ownership + moves |
| `eq_augs.export_bundle` | Hook into `inventory_parser.export_bundle` | Add optional Slot2 section to `ExportBundle` |
| `eq_augs.excel_export` | `inventory_parser.excel_export` | Sheets: `Augs`, `Need to Farm`, `Ranked Augs`, `Legend` |
| `eq_augs.html_export` | `inventory_parser.html_export` / `team_report.html` | New section in team HTML |
| GUI controls | `data/gui/setup.html` + `setup.js` + `web_api.py` | Artisan's Prize + Include Anniversary (no profile dropdown) |

## Character class (Chest armor)

When the inventory filename has no class (`Name_server-Inventory.txt`), class is
detected from the **equipped Chest** item:

1. Look up the Chest item id on raidloot (`items?name={id}`) — `Class: ROG`
2. If missing, EQ Resource (`items.php?id=`) — `Class: Rogue`
3. Cache under `%LOCALAPPDATA%\EQ Augs\item_class_cache.json`

That class drives Feet AC rules and the Dex / INT / WIS aug catalog for the
character. Profile is **auto-detected only** (no GUI override); fallback profile
is used only when class cannot be detected.

## Deliberate divergence

Inventory Parser **skips** locations containing `-Slot` when building parent gear rows
(`extract_equipped_items`). EQ Augs **reads** type 7/8 dump SlotN rows for equipped gear bases.

When merging:

1. Do **not** change IP parent-gear extraction semantics.
2. Add a parallel function (this app's `extract_slot2_augs`) that walks the same dump and
   numbers Ear/Wrist/Fingers the same way IP does for parents.
3. Share one TSV parse path (`parse_inventory_file`) to avoid duplicate filename/encoding logic.

## Shared conventions (already aligned)

- Filename: `{Char}_{Server}[-CLASS]-Inventory.txt`
- TSV columns: `Location`, `Name`, `ID`, `Count`, `Slots`
- Ear / Fingers / Wrist numbering by appearance order of parent rows → `Ear-1`, `Ear-2`, …
- Equipped bases: `EQUIPMENT_SLOT_BASES` (same set as IP)
- Report slot order: visible slots then non-visible (same as IP team gear)

## GUI merge hooks

Add to Inventory Parser setup UI:

1. **Artisan's Prize owned** checkbox (global per generate run).
2. **Include Anniversary augs** checkbox (default off).
3. Optional: enable/disable “Slot2 Augs” sheet/section (chip or include toggle).
4. **Advanced weights** (single character only): tab next to Aug options with
   compact editable class default weights; session-only via `session_weights` on
   generate — do not persist to AppData unless IP already has a weight editor.

Do **not** add a Stat profile dropdown — IP should use Chest/filename class → profile
the same way EQ Augs does.

EQ Augs already mirrors IP roster UX (do not reinvent on merge):

- Folder pick → character checkbox modal with **server filter**
- Add selected from multiple folders / servers into one roster
- Click-select, Ctrl+click multi-select, **Up / Down / Remove / Clear**
- Persist column order via `%LOCALAPPDATA%\EQ Augs\settings.json` → `character_column_order`
- Show server under character name when roster spans multiple servers
- Export prefix: single char name, else shared server, else `Team`
- Success toasts: short lifetime, bottom-left (do not cover Generate)

Wire in `WebApi.generate_report` after `build_export_bundle`:

- Call `fetch_catalog(profile)` (network; may be slow — keep on background thread).
- Filter anniversary gems unless `include_anniversary`.
- Attach Slot2 character reports onto the bundle.
- Excel writer adds sheets; HTML serializer adds a `slot2` key for `team_report.html`.
- Reuse IP `build_column_roster` / `save_character_column_order` instead of `eq_augs.roster`.

## Raidloot / cache

- URLs live in `eq_augs.profiles.RAIDLOOT_URLS`.
- Cache path: `%LOCALAPPDATA%\EQ Augs\raidloot_cache.json`
- Item socket cache: `%LOCALAPPDATA%\EQ Augs\item_sockets_cache.json`
- EQ Resource aug stats: `%LOCALAPPDATA%\EQ Augs\eqresource_aug_cache.json`
- Expansion names: `%LOCALAPPDATA%\EQ Augs\eqresource_expansion_cache.json`
- On merge, consider `%LOCALAPPDATA%\Inventory Parser\…` instead.
- No public JSON API — HTML parse with disk cache fallback.
- Always inject Artisan's Prize stub as Ear-only (`88785`) for checkbox behavior.

## Artisan's Prize rules

- Fits **Ear only** (not Charm/Range/general).
- When checkbox **off**: exclude from recommendations (still may appear in reference list optionally).
- When checkbox **on**: treat as Ear BiS when currently equipped on Ear; otherwise
  recommend for empty/fallen-off Ear holes (not forced onto Ear-1 over locked BiS).
- Also treated as owned when the item ID appears in the inventory dump.
- If currently equipped on Ear → status `bis`.

## Anniversary augs

Names containing **`Gem of Distant Echoes`** (case-insensitive) are anniversary
vendor gems (time-limited). Module: `eq_augs.anniversary`.

- Default: **excluded** from catalog used for recommendations and ranked reference.
- GUI / CLI `--include-anniversary`: include them.
- Does not match Shards / Stones / Bands of Distant Echoes.

## Ownership / Need to farm

- `collect_owned_item_ids` — every non-empty item ID in the dump (bags, bank, equipped).
- `collect_owned_item_names` — casefolded names for craft-component matching.
- Recommended upgrades show **Owned**, **Move from {slot}**, or **Need to farm**.
- **Need to farm** list / Excel sheet = recommended upgrades whose ID is not owned
  (and not a cross-slot move of an already-equipped piece — including pieces freed
  when a priority slot takes a better BiS).
- Craft empower components (`eq_augs.craft_components`): when a Need-to-farm aug
  matches a known affix line, note **Have {Focus/ore}** if that component is in the
  dump (containers are not tracked). Mapping:
  - Unraveling Order → Unraveling Focus of Fortitude
  - Phantasmal Luclinite → Otherworldly Focus of Fortitude
  - Perpetual Reverie → Gallant Focus of Fortitude
  - Uprising → Fortitude Focus of Uprising
  - Luclinite Ensanguined → Ossified Bloodied Ore
- Item hyperlinks → `https://items.eqresource.com/items.php?id={id}`.
- Expansion from EQ Resource `expacimages/{code}.jpg` for recommended IDs only.

## Feet high-AC rule

For classes **WAR, MNK, RNG, BST, BRD**, Feet Slot2 uses an **AC-heavy slot
weight overlay** (see `data/weights/slot_overlays.json` + `_apply_feet_ac_dominance`):
**AC is boosted and scoring becomes AC-only** for that slot, so any AC edge beats
focus/ATK/HP differences. Equal-AC ties still break on HP then name via `rank_key`.
Ranking otherwise uses role → class weighted scores (`eq_augs.weights`).

Those same classes also treat **Feet as a priority assignment slot** (after Range
and Charm): its BiS is claimed before general holes because fewer augs are
competitive there under the AC overlay.

- Requires class abbr on the inventory filename (`{Char}_{Server}-WAR-Inventory.txt`),
  roster `classAbbr`, or Chest-detected class; without class, the profile default
  role weights are used.
- Does **not** apply to PAL, SHD, ROG, BER even though they share the Dex catalog.

## Weighted scoring

Recommendations rank legal (slot-fitting) augs by:

`score = Σ(stat × weight)` where weights = role base ⊕ class modifiers ⊕ slot overlay.

Simplified role focus (class modifiers empty by default):

| Role | Focus stats |
|------|-------------|
| tank | AC, HDex |
| priest | HWis |
| pure_caster | Spell Damage, HInt |
| melee_dps / hybrid_dps | HDex |

- Packaged tables: `eq_augs/data/weights/{roles,classes,slot_overlays}.json`
- Optional overrides: `%LOCALAPPDATA%\EQ Augs\weight_overrides.json`
- Fit filters (Charm/Range exclusions, shield-only, Ear/Artisan's Prize, anniversary)
  stay orthogonal to scoring. Advanced GUI always surfaces AC / HDex / HInt / HWis /
  Spell Damage; Accuracy / Combat Effects / Shielding / Stun Resist stay excluded.
- Catalog fetch remains Dex/INT/WIS raidloot filters; weights refine ranking
  within that catalog.

## Lore unique assignment / missing BiS loadout

Recommendations treat the character's equipped type 7/8 augs **as a set**:

1. Build an **ideal unique loadout** with **Range → Charm → Feet (when high-AC
   overlay applies) → remaining slots** first (few augs fit those holes).
2. **Priority slots** (Range, Charm, Feet-when-needed) claim their ideal BiS even
   when that aug is equipped elsewhere — recommend **moving** it there and
   replacing the donor slot.
3. When a priority slot will take a **better missing** BiS, a displaced piece that
   is another slot's ideal may be recommended as a **move** (Owned), not farmed again.
4. Ideal pieces already equipped on **general** slots are kept unless claimed by a
   priority slot (no general↔general reshuffle). What matters is that the best
   owned/farmable set is equipped, not which general hole holds which piece.
5. Only **missing** ideal augs are otherwise recommended — empty holes first,
   then non-ideal currents (priority slots before general).
6. Never recommend an aug that ranks worse than the slot's current aug.
7. If current aug is missing from the raidloot catalog, look up stats on
   **EQ Resource** (`items.eqresource.com`) for Focus/AC/HP comparison
   (cached under `%LOCALAPPDATA%\EQ Augs\eqresource_aug_cache.json`).
   Notes no longer append `stats via EQ Resource` when that fallback is used.
   Still `unknown` only when EQ Resource also misses.

Upgrade reports list all graded slots (`upgrade` / `empty` / `unknown` / `bis`).
BiS rows leave **Upgrade to** blank. Ignored (`no_fit`) slots are omitted.

## Range bows (Slot4)

A Range item is treated as a **bow** when both are true:

1. The dump lists `Range-Slot1` through `Range-Slot4`
2. The Range parent item name contains `bow` / `crossbow` (case-insensitive)

- Non-bow Range → type 7/8 from `Range-Slot2`
- Bow Range → type 7/8 from `Range-Slot4`

See `eq_augs.parser.is_range_bow`.

## Type 7/8 socket map (parent item ID)

Inventory dumps do **not** label aug hole types. EQ Augs resolves the type 7/8
dump slot from the parent gear item ID:

1. Fetch raidloot `https://www.raidloot.com/items?name={item_id}`
2. Parse `Slot N, type T` labels
3. Use the **lowest** SlotN where `T` is 7 or 8
4. If raidloot has no sockets, fall back to EQ Resource
   `items.php?id={id}` (`getAugs('T','id','N')`)
5. On total miss: Slot2 heuristic (Range bow → Slot4)

Module: `eq_augs.item_sockets`. Cache:
`%LOCALAPPDATA%\EQ Augs\item_sockets_cache.json`

Examples: Head Resonant Fracture → Slot2; Ear Resonant Fracture → Slot3;
Face evolver (Vortex mask) → Slot4.

Primary is skipped for lookup; Secondary only when shield-named.

## Primary / Secondary / shields

Primary and Secondary **weapons** are ignored (no BiS recommendation).

Secondary is evaluated only when the parent item name contains **Shield** or
**Aegis** (case-insensitive; see `eq_augs.parser.parent_name_is_shield`).

Shield Secondary recommendations use raidloot augs with:

- `Slot: Secondary`
- `Restrictions: Shield Only`

Fetched from `SHIELD_AUG_URL` (`type=Aug_Shield`) and merged into the profile
catalog (`AugCandidate.shield_only`). Ranked by **AC**, then HP.

## Charm / Range

Most modern type 7/8 augs: `Slot: All except Charm, Range, Primary, Secondary, Ammo`.

Some (e.g. Joy of the Dancer): `All except Primary, Secondary, Ammo` → **fits Charm and Range**.

Some: `All except Range, …` → fits Charm but not Range.

Recommendation filter: `AugCandidate.fits_gear_slot(gear_slot)`.

## Export merge points

### Excel (`excel_export.write_workbook`)

Sheets:

1. **Augs** — graded slots; Owned? / Expansion columns; EQ Resource hyperlinks.
2. **Need to Farm** — missing recommended upgrades; aug cell notes Have Focus/ore when owned.
3. **Ranked Augs** — top N from roster profiles.
4. **Legend** — status + ownership meanings.

Status colors: bis green, upgrade amber, empty red, unknown blue-gray, no_fit gray.

### HTML (`html_export` / `team_report.html`)

- Add `slot2` object to injected JSON (see `eq_augs.html_export.serialize_report`).
- Render upgrades + **Need to farm** + ranked list (patterns in `eq_augs/data/report.html`).
- Item links → EQ Resource; ownership / move / craft-component badges; expansion column.
- Collapsible cards: Stat summary, Slot recommendations, Need to farm, Ranked reference;
  Need to farm and Ranked reference start collapsed.
- Report meta line: short catalog time (`YYYY-MM-DD HH:MM UTC`) plus `EQ Augs {version}`
  from `__version__` (Excel Ranked Augs header uses the same).
- Top bar: character filter beside status legend (BiS / Upgrade / Empty / Unknown); no row-count
  badge. Right side embeds circular `eq-report-logo.png` via `logoDataUri` in report JSON.
- Packaged branding: `scripts/prepare_app_icon.py` (exe/window `eq-icon.ico`) and
  `scripts/prepare_report_logo.py` (HTML header mark).

## Dependencies

Same as Inventory Parser today:

- `openpyxl>=3.1`
- `pywebview>=5.0`

No BeautifulSoup — stdlib `html.parser` + regex.

## Tests to port

- `tests/test_parser.py` — Slot2 extraction + owned IDs (inventory dump fixtures)
- `tests/test_raidloot.py` — slot restriction strings + HTML fixture
- `tests/test_weights.py` — role/class merge, Feet AC-only overlay, shield overlay
- `tests/test_compare.py` — Artisan's Prize, Charm/Range/Feet priority moves, displaced Range→Head
- `tests/test_item_sockets.py` — parent socket map parse + Face evolver Slot4
- `tests/test_eqresource_augs.py` — EQ Resource stats + expansion parse + ownership
- `tests/test_anniversary.py` — Distant Echoes gem filter
- `tests/test_html_export.py` — serialize farm list + EQ Resource URL payload
- `tests/test_craft_components.py` — affix → Focus/ore mapping + ownership helpers

Use fixture `tests/fixtures/raidloot_dex_sample.html` (no live network in CI).
Socket fixtures: `raidloot_item_*.html`, `eqresource_item_168096.html`.
Aug/expansion fixtures: `eqresource_aug_*.html`, `eqresource_chest_*.html`.

## Suggested merge PR sequence

1. Lift `extract_slot2_augs` + `collect_owned_item_ids` + unit tests into IP `parser.py` (no GUI yet).
2. Add `slot2_augs` package (profiles, anniversary, raidloot, eqresource, compare) + caches under IP appdata.
3. Extend `ExportBundle` + Excel/HTML writers behind a feature flag/chip.
4. Add GUI controls (Artisan's Prize, Include Anniversary) and wire `generate_report`.
5. Delete standalone EQ Augs app or keep as thin launcher that calls IP.

## Version / branding

- Standalone package name: `eq-augs` (`eq_augs`), version **`0.3.7`**
- Entry points: `eq-augs`, `eq-augs-gui`, `run_gui.bat`
- One-file Windows GUI: run `build_exe.bat` → `dist\EQAugs-<version>.exe`
- Icons: `Icon/Icon.png` / `Icon/report-logo-source.png` → `src/eq_augs/assets/`
- After merge: fold into `inventory-parser` / `inventory-parser-gui`; drop duplicate pywebview window or add a mode tab.
