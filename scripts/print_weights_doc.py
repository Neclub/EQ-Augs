"""Generate docs/Aug_Selection_Weights.txt from packaged weight JSON."""

from __future__ import annotations

import json
from pathlib import Path

from eq_augs.aug_stats import STAT_DISPLAY
from eq_augs.weights import clear_weights_cache, class_role, resolve_weights

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "src" / "eq_augs" / "data" / "weights"
OUT = ROOT / "docs" / "Aug_Selection_Weights.txt"

ROLE_ORDER = ("tank", "priest", "pure_caster", "melee_dps", "hybrid_dps")
ROLE_TITLES = {
    "tank": "Tank",
    "priest": "Priest",
    "pure_caster": "Pure Caster",
    "melee_dps": "Melee DPS",
    "hybrid_dps": "Hybrid DPS",
}
CLASS_ORDER = (
    "WAR",
    "SHD",
    "PAL",
    "CLR",
    "DRU",
    "SHM",
    "WIZ",
    "MAG",
    "NEC",
    "ENC",
    "ROG",
    "MNK",
    "BER",
    "RNG",
    "BST",
    "BRD",
)


def fmt_weights(weights: dict[str, float], indent: str = "  ") -> str:
    lines: list[str] = []
    for key, value in sorted(weights.items(), key=lambda kv: (-kv[1], kv[0])):
        label = STAT_DISPLAY.get(key, key)
        lines.append(f"{indent}{label:<18} {value:7.2f}")
    return "\n".join(lines)


def main() -> None:
    clear_weights_cache()
    roles = json.loads((WEIGHTS / "roles.json").read_text(encoding="utf-8"))
    classes = json.loads((WEIGHTS / "classes.json").read_text(encoding="utf-8"))
    overlays = json.loads((WEIGHTS / "slot_overlays.json").read_text(encoding="utf-8"))

    out: list[str] = []
    out.append("EQ Augs — Aug Selection Weights")
    out.append("=" * 72)
    out.append("")
    out.append(
        "Source files: src/eq_augs/data/weights/{roles,classes,slot_overlays}.json"
    )
    out.append(
        "Optional overrides: %LOCALAPPDATA%\\EQ Augs\\weight_overrides.json"
    )
    out.append(
        "Score = sum(stat_value * weight) for each known stat on the aug."
    )
    out.append(
        "Missing stats contribute 0. Fit filters (Charm/Range/Feet/Shield,"
    )
    out.append(
        "Artisan's Prize, anniversary Distant Echoes gems) are separate from scoring."
    )
    out.append("")
    out.append("Simplified focus stats:")
    out.append("  tank:        AC (10) > HDex (8)")
    out.append("  priest:      HWis (10)")
    out.append("  pure_caster: Spell Damage (10) > HInt/HWis/HDex (1)")
    out.append("  melee_dps / hybrid_dps: HDex (10)")
    out.append("")

    out.append("1. ROLE BASE WEIGHTS")
    out.append("-" * 72)
    for rid in ROLE_ORDER:
        out.append("")
        out.append(f"{ROLE_TITLES[rid]} ({rid})")
        out.append(fmt_weights(roles["roles"][rid]))

    out.append("")
    out.append("2. CLASS MODIFIERS (added to role base)")
    out.append("-" * 72)
    by_role: dict[str, list[tuple[str, dict]]] = {}
    for abbr, entry in classes["classes"].items():
        by_role.setdefault(entry["role"], []).append((abbr, entry))
    for rid in ROLE_ORDER:
        out.append("")
        out.append(f"--- {ROLE_TITLES[rid]} ---")
        for abbr, entry in sorted(by_role.get(rid, [])):
            mods = entry.get("modifiers") or {}
            out.append(f"{abbr}  catalog={entry['profile']}")
            out.append(fmt_weights(mods) if mods else "  (no modifiers)")

    out.append("")
    out.append("3. SLOT OVERLAYS (added when slot/class match)")
    out.append("-" * 72)
    for ov in overlays["overlays"]:
        out.append("")
        out.append(str(ov["id"]))
        slots = ", ".join(ov.get("slots") or [])
        out.append(f"  slots: {slots}")
        cls = ov.get("classes")
        out.append(f"  classes: {', '.join(cls) if cls else '(all)'}")
        if ov.get("require_shield"):
            out.append("  require_shield: true")
        out.append(fmt_weights(ov.get("modifiers") or {}))
        if ov.get("id") == "feet_high_ac":
            out.append(
                "  note: effective Feet weights become AC-only "
                "(other stats dropped after merge)"
            )

    out.append("")
    out.append("4. EFFECTIVE WEIGHTS BY CLASS (Head slot — no overlay)")
    out.append("-" * 72)
    for abbr in CLASS_ORDER:
        weights = resolve_weights(abbr, "Head")
        role = class_role(abbr)
        out.append("")
        out.append(f"{abbr}  role={role}")
        out.append(fmt_weights(weights))

    out.append("")
    out.append("5. FEET OVERLAY EFFECTIVE (WAR / MNK / RNG / BST / BRD)")
    out.append("-" * 72)
    for abbr in ("WAR", "MNK", "RNG", "BST", "BRD", "ROG"):
        weights = resolve_weights(abbr, "Feet")
        out.append("")
        out.append(f"{abbr} Feet")
        out.append(fmt_weights(weights))

    out.append("")
    out.append("6. SHIELD SECONDARY OVERLAY (PAL Secondary shield)")
    out.append("-" * 72)
    weights = resolve_weights("PAL", "Secondary", secondary_is_shield=True)
    out.append("")
    out.append("PAL Secondary (shield)")
    out.append(fmt_weights(weights))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
