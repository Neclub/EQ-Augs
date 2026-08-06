"""Print eq_augs package version (one line) for build scripts."""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from package_version import read_package_version

if __name__ == "__main__":
    print(read_package_version())
