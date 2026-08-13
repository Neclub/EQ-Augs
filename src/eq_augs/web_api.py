"""Python API exposed to the HTML GUI via pywebview."""

from __future__ import annotations

import json
import threading
import time
import traceback
import webbrowser
from pathlib import Path

import webview

from eq_augs import __version__
from eq_augs.excel_export import write_workbook
from eq_augs.export_bundle import build_export_bundle, default_profile_from_paths, report_progress
from eq_augs.html_export import html_path_for_workbook, write_html
from eq_augs.profiles import normalize_profile
from eq_augs.roster import (
    build_roster,
    discover_folder_character_choices,
    export_prefix_from_roster,
    paths_for_removal,
    save_character_column_order,
    saved_character_column_order,
    unique_servers,
)
from eq_augs.web_bridge import eq_logo_data_uri
from eq_augs.weights import default_class_weights, sanitize_weight_map

_PROGRESS_WRITE = (0.95, 1.0)


def _downloads_dir() -> Path:
    return Path.home() / "Downloads"


def _roster_entry_dict(entry) -> dict:
    return {
        "personaKey": entry.persona_key,
        "character": entry.character,
        "server": entry.server,
        "classAbbr": entry.class_abbr,
        "path": entry.path,
        "displayName": entry.display_name,
    }


def _choice_dict(choice) -> dict:
    return {
        "personaKey": choice.persona_key,
        "character": choice.character,
        "server": choice.server,
        "classAbbr": choice.class_abbr,
        "path": choice.path,
        "paths": [choice.path],
        "summary": choice.summary,
        "serverDisplay": choice.server,
    }


class WebApi:
    def __init__(self) -> None:
        self._window: webview.Window | None = None
        self._file_paths: list[str] = []
        self._profile: str = "dex"
        self._artisans_prize: bool = False
        self._include_anniversary: bool = False
        self._output_format: str = "both"
        self._output_dir: str = str(_downloads_dir())

    def bind_window(self, window: webview.Window) -> None:
        self._window = window

    def get_version(self) -> dict:
        return {"version": __version__, "logoDataUri": eq_logo_data_uri()}

    def get_gui_prefs(self) -> dict:
        return {
            "profile": self._profile,
            "artisansPrizeOwned": self._artisans_prize,
            "includeAnniversary": self._include_anniversary,
            "outputFormat": self._output_format,
            "outputDir": self._output_dir,
        }

    def set_profile(self, profile: str) -> dict:
        self._profile = normalize_profile(profile)
        return {"profile": self._profile}

    def set_artisans_prize(self, owned: bool) -> dict:
        self._artisans_prize = bool(owned)
        return {"artisansPrizeOwned": self._artisans_prize}

    def set_include_anniversary(self, include: bool) -> dict:
        self._include_anniversary = bool(include)
        return {"includeAnniversary": self._include_anniversary}

    def get_class_weight_defaults(
        self, class_abbr: str | None = None, profile: str | None = None
    ) -> dict:
        """Return Head-slot default weights for Advanced aug options (single char)."""
        use_profile = normalize_profile(profile) if profile else None
        return default_class_weights(class_abbr, profile=use_profile)

    def set_output_format(self, format: str) -> dict:
        if format in ("excel", "html", "both"):
            self._output_format = format
        return {"outputFormat": self._output_format}

    def pick_folder(self) -> str | None:
        """Return selected folder path, or None if cancelled (Inventory Parser style)."""
        window = self._window
        if window is None:
            return None
        result = window.create_file_dialog(webview.FileDialog.FOLDER)
        if not result:
            return None
        folder = result[0] if isinstance(result, (list, tuple)) else result
        return str(folder)

    def discover_folder_choices(self, folder: str) -> dict:
        choices = discover_folder_character_choices(folder)
        servers = unique_servers(choices)
        return {
            "folder": str(folder),
            "choices": [_choice_dict(c) for c in choices],
            "servers": [{"slug": s, "label": s} for s in servers],
        }

    def build_roster(self, paths: list[str]) -> list[dict]:
        self._file_paths = [str(p) for p in paths]
        entries = build_roster(
            paths,
            saved_character_column_order(),
            detect_chest_class=True,
        )
        return [_roster_entry_dict(e) for e in entries]

    def save_roster_order(self, persona_keys: list[str]) -> None:
        save_character_column_order([str(k) for k in persona_keys if k])

    def paths_for_removal(
        self,
        removing_keys: list[str],
        roster: list[dict],
        paths: list[str],
    ) -> list[str]:
        entries = build_roster(paths, [e.get("personaKey", "") for e in roster])
        # Prefer paths from the provided roster order when available
        from eq_augs.roster import RosterEntry, persona_key

        rebuilt: list = []
        for e in roster:
            rebuilt.append(
                RosterEntry(
                    persona_key=e.get("personaKey")
                    or persona_key(e.get("character", ""), e.get("server", ""), e.get("classAbbr")),
                    character=e.get("character", ""),
                    server=e.get("server", ""),
                    class_abbr=e.get("classAbbr"),
                    path=e.get("path", ""),
                )
            )
        drop = paths_for_removal(removing_keys, rebuilt if rebuilt else entries)
        return drop

    def default_output_dir_label(self, paths: list[str]) -> str:
        roster = build_roster(paths, saved_character_column_order())
        prefix = export_prefix_from_roster(roster)
        return str(Path(self._output_dir) / f"{prefix}_Slot2_Augs.xlsx")

    def pick_output_dir(self) -> dict:
        window = self._window
        if window is None:
            return {"ok": False, "error": "Window not ready"}
        result = window.create_file_dialog(webview.FileDialog.FOLDER)
        if not result:
            return {"ok": False, "cancelled": True}
        folder = result[0] if isinstance(result, (list, tuple)) else result
        self._output_dir = str(folder)
        return {"ok": True, "outputDir": self._output_dir}

    def clear_files(self) -> dict:
        self._file_paths = []
        return {"ok": True}

    def generate_report(self, options: dict | None = None) -> dict:
        """Start report generation on a background thread; returns immediately."""
        opts = options or {}
        if "profile" in opts:
            self._profile = normalize_profile(str(opts["profile"]))
        if "artisansPrizeOwned" in opts:
            self._artisans_prize = bool(opts["artisansPrizeOwned"])
        if "includeAnniversary" in opts:
            self._include_anniversary = bool(opts["includeAnniversary"])
        if "outputFormat" in opts:
            fmt = opts["outputFormat"]
            if fmt in ("excel", "html", "both"):
                self._output_format = fmt
        if "outputDir" in opts and opts["outputDir"]:
            self._output_dir = str(opts["outputDir"])

        paths = [str(p) for p in (opts.get("filePaths") or self._file_paths)]
        persona_order = [str(k) for k in (opts.get("personaOrder") or []) if k]
        if persona_order:
            save_character_column_order(persona_order)

        if not paths:
            return {"ok": False, "error": "No inventory files loaded."}

        profile = self._profile
        prize = self._artisans_prize
        include_anniversary = self._include_anniversary
        fmt = self._output_format
        out_dir = Path(self._output_dir)
        self._file_paths = paths

        session_weights = None
        if opts.get("advancedWeights") and len(paths) == 1:
            raw = opts.get("sessionWeights")
            if isinstance(raw, dict):
                cleaned = sanitize_weight_map(raw)
                if cleaned:
                    session_weights = cleaned

        def worker() -> None:
            t0 = time.perf_counter()

            def on_progress(payload: dict) -> None:
                self._notify_progress(payload)

            def elapsed() -> float:
                return round(time.perf_counter() - t0, 1)

            try:
                bundle = build_export_bundle(
                    paths,
                    profile=profile,
                    artisans_prize_owned=prize,
                    include_anniversary=include_anniversary,
                    persona_order=persona_order or None,
                    session_weights=session_weights,
                    on_progress=on_progress,
                )
                if not bundle.characters:
                    self._notify_complete(
                        {
                            "ok": False,
                            "error": "No inventory dumps could be parsed.",
                            "elapsedSeconds": elapsed(),
                        }
                    )
                    return

                prefix = bundle.export_prefix or bundle.server or "Team"
                xlsx_path = out_dir / f"{prefix}_Slot2_Augs.xlsx"
                saved_xlsx = None
                saved_html = None

                write_steps: list[str] = []
                if fmt in ("excel", "both"):
                    write_steps.append("excel")
                if fmt in ("html", "both"):
                    write_steps.append("html")
                w0, w1 = _PROGRESS_WRITE
                n_write = len(write_steps) or 1

                for i, step in enumerate(write_steps, start=1):
                    label = (
                        "Writing Excel…"
                        if step == "excel"
                        else "Writing HTML…"
                    )
                    report_progress(on_progress, label, w0, w1, i - 1, n_write)
                    if step == "excel":
                        saved_xlsx = str(write_workbook(bundle, xlsx_path))
                    else:
                        html_target = (
                            html_path_for_workbook(xlsx_path)
                            if fmt == "both"
                            else out_dir / f"{prefix}_Slot2_Augs.html"
                        )
                        saved_html = str(write_html(bundle, html_target))
                        try:
                            webbrowser.open(Path(saved_html).resolve().as_uri())
                        except OSError:
                            pass
                    report_progress(on_progress, label, w0, w1, i, n_write)

                if not write_steps:
                    report_progress(on_progress, "Done", w0, w1, 1, 1)

                self._notify_complete(
                    {
                        "ok": True,
                        "xlsx": saved_xlsx,
                        "html": saved_html,
                        "warnings": bundle.warnings,
                        "characterCount": len(bundle.characters),
                        "fromCache": bundle.catalog.from_cache,
                        "elapsedSeconds": elapsed(),
                    }
                )
            except Exception as exc:
                self._notify_complete(
                    {
                        "ok": False,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                        "elapsedSeconds": elapsed(),
                    }
                )

        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True, "started": True}

    def infer_profile(self, paths: list[str]) -> dict:
        profile = default_profile_from_paths(paths)
        self._profile = profile
        return {"profile": profile}

    def _notify_progress(self, payload: dict) -> None:
        window = self._window
        if window is None:
            return
        try:
            window.evaluate_js(
                f"window.onGenerateProgress && window.onGenerateProgress({json.dumps(payload)})"
            )
        except Exception:
            pass

    def _notify_complete(self, result: dict) -> None:
        window = self._window
        if window is None:
            return
        payload = json.dumps(result)
        try:
            window.evaluate_js(f"window.onGenerateComplete({payload})")
        except Exception:
            pass
