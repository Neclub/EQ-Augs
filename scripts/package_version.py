"""Read EQ Augs package version from src for build scripts."""
from __future__ import annotations

import re
from pathlib import Path


def read_package_version(root: Path | None = None) -> str:
    if root is None:
        root = Path(__file__).resolve().parent.parent
    init_py = root / "src" / "eq_augs" / "__init__.py"
    text = init_py.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    if not m:
        raise RuntimeError(f"Could not parse __version__ from {init_py}")
    return m.group(1).strip()


def exe_name_for_version(version: str, basename: str = "EQAugs") -> str:
    return f"{basename}-{version}"
