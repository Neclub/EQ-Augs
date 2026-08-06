"""Invoke PyInstaller for the EQ Augs GUI (one-file exe)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from package_version import exe_name_for_version, read_package_version

_ROOT = Path(__file__).resolve().parent.parent


def _version_to_quad(version: str) -> tuple[int, int, int, int]:
    parts: list[int] = []
    for seg in version.split("."):
        num = ""
        for c in seg:
            if c.isdigit():
                num += c
            else:
                break
        parts.append(int(num) if num else 0)
        if len(parts) >= 4:
            break
    while len(parts) < 4:
        parts.append(0)
    return (parts[0], parts[1], parts[2], parts[3])


def _write_version_info(path: Path, version: str, exe_name: str) -> None:
    a, b, c, d = _version_to_quad(version)
    quad_str = f"({a}, {b}, {c}, {d})"
    file_ver_str = f"{a}.{b}.{c}.{d}"
    orig = f"{exe_name}.exe"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={quad_str},
    prodvers={quad_str},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [
        StringStruct('CompanyName', ''),
        StringStruct('FileDescription', 'EQ Augs — Slot2 Type 7/8 Checker'),
        StringStruct('FileVersion', '{file_ver_str}'),
        StringStruct('InternalName', '{exe_name}'),
        StringStruct('LegalCopyright', ''),
        StringStruct('OriginalFilename', '{orig}'),
        StringStruct('ProductName', 'EQ Augs'),
        StringStruct('ProductVersion', '{version}')])
      ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
        encoding="utf-8",
    )


def main() -> int:
    version = read_package_version(_ROOT)
    exe_name = exe_name_for_version(version)
    version_info = _ROOT / "build" / "EQAugs_version_info.txt"
    _write_version_info(version_info, version, exe_name)

    entry = _ROOT / "scripts" / "pyinstaller_gui.py"
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--noconsole",
        "--name",
        exe_name,
        "--exclude-module",
        "numpy",
        "--exclude-module",
        "pandas",
        "--exclude-module",
        "matplotlib",
        "--collect-all",
        "webview",
        "--hidden-import",
        "webview.platforms.winforms",
        "--collect-data",
        "eq_augs",
        "--hidden-import",
        "eq_augs.package_data",
        "--hidden-import",
        "eq_augs.web_gui",
        "--hidden-import",
        "eq_augs.web_api",
        "--hidden-import",
        "eq_augs.weights",
        "--hidden-import",
        "eq_augs.aug_stats",
        "--distpath",
        str(_ROOT / "dist"),
        "--workpath",
        str(_ROOT / "build" / "pyinstaller"),
        "--specpath",
        str(_ROOT / "build"),
        str(entry),
    ]
    if sys.platform == "win32":
        args.extend(["--version-file", str(version_info.resolve())])
        for icon_name in ("eq-icon.ico", "eq-icon.png"):
            icon = _ROOT / "src" / "eq_augs" / "assets" / icon_name
            if icon.is_file():
                args.extend(["--icon", str(icon.resolve())])
                break

    print(f"Package version: {version}")
    print(f"Output exe: {_ROOT / 'dist' / f'{exe_name}.exe'}")
    print("Running:", " ".join(args))
    return subprocess.call(args, cwd=str(_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
