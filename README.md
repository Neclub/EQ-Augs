# EQ Augs

Figure out which Slot2 type 7/8 augs you’re missing — and which ones you already own.

EQ Augs reads your EverQuest inventory dumps, compares equipped type 7/8 augs against live [raidloot.com](https://www.raidloot.com) rankings, and builds a report of upgrades, bag/bank ownership, and a **Need to farm** list. Charm, Range, and Feet (for high-AC classes) get special attention so priority holes show up first.

**Version:** 0.3.2  
**Current build:** [EQAugs-0.3.2.exe](https://github.com/Neclub/EQ-Augs/releases/latest/download/EQAugs-0.3.2.exe)
([all releases](https://github.com/Neclub/EQ-Augs/releases/latest))

![EQ Augs setup window](docs/images/gui-setup.png)

## How to use it

1. **Download** the current build above and run `EQAugs-0.3.2.exe` (no install needed).
2. Click **EQ Folder** and choose the folder with your `*-Inventory.txt` dumps (or drop the files into the Characters list).
3. Optionally set **Aug options** — Artisan’s Prize ownership, anniversary gems, etc.
4. Pick an **Output folder** and format (Excel, HTML, or both).
5. Click **Generate Report**.

The report shows what you have equipped vs what’s recommended, marks pieces you already own (bags/bank count), and lists what’s still to farm. Item names link to EQ Resource.

### Tips

- Leave **Include Anniversary augs** off unless you want Gems of Distant Echoes in the recommendations.
- **Advanced weights** (single character only) lets you tweak scoring for one generate; leave **Use weight overrides** unchecked to stick with class defaults.

## For developers

```bat
run_gui.bat
py -m pip install -e ".[dev]"
py -m pytest
build_exe.bat
```

Local build output: `dist\EQAugs-0.3.2.exe`

Merge notes for Inventory Parser: [MERGE_NOTES.md](MERGE_NOTES.md)
