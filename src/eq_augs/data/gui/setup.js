/* EQ Augs — HTML setup page (roster UX mirrors Inventory Parser) */

const state = {
  filePaths: [],
  roster: [],
  selectedRoster: new Set(),
  profile: "dex",
  artisansPrizeOwned: false,
  includeAnniversary: false,
  optionsTab: "options", // "options" | "advanced"
  useWeightOverrides: false,
  weightDefaults: null,
  weightEdits: null,
  weightsClassKey: null,
  outputFormat: "both",
  outputDir: "",
  generating: false,
};

const OUTPUT_FORMATS = ["excel", "html", "both"];
const $ = (id) => document.getElementById(id);

function api(method, ...args) {
  if (!window.pywebview || !pywebview.api || !pywebview.api[method]) {
    return Promise.reject(new Error("App API not available."));
  }
  return Promise.resolve(pywebview.api[method](...args));
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/`/g, "&#96;");
}

function showToast(message, isError = false) {
  const el = $("toast");
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.classList.remove("hidden");
  clearTimeout(showToast._timer);
  const ms = isError ? 4500 : 2200;
  showToast._timer = setTimeout(() => el.classList.add("hidden"), ms);
}

function showModal(html) {
  $("modalRoot").innerHTML = `<div class="modal-backdrop" id="modalBackdrop">${html}</div>`;
  const backdrop = $("modalBackdrop");
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) closeModal();
  });
}

function closeModal() {
  $("modalRoot").innerHTML = "";
}

function toggleChip(el, on) {
  el.classList.toggle("on", on);
}

function syncOutputFormatChips() {
  OUTPUT_FORMATS.forEach((fmt) => {
    const chip = $(`chipFormat${fmt[0].toUpperCase()}${fmt.slice(1)}`);
    if (chip) toggleChip(chip, state.outputFormat === fmt);
  });
}

function createCharCard(entry, { showServer } = {}) {
  const wrap = document.createElement("div");
  wrap.className = "char-card-inner";
  const cls = entry.classAbbr
    ? `<span class="class-badge">${escapeHtml(entry.classAbbr)}</span>`
    : "";
  const serverLine =
    showServer && entry.server
      ? `<div class="char-server">${escapeHtml(entry.server)}</div>`
      : "";
  wrap.innerHTML = `<div class="char-meta">
    <div class="char-row-top"><span class="char-name">${escapeHtml(entry.character)}</span>${cls}</div>
    ${serverLine}
  </div>`;
  return wrap;
}

function renderRoster() {
  const list = $("rosterList");
  list.innerHTML = "";
  const servers = new Set(state.roster.map((e) => (e.server || "").toLowerCase()).filter(Boolean));
  const showServer = servers.size > 1;
  state.roster.forEach((entry, idx) => {
    const li = document.createElement("li");
    li.className = "roster-item";
    li.dataset.index = String(idx);
    if (state.selectedRoster.has(idx)) li.classList.add("selected");
    li.appendChild(createCharCard(entry, { showServer }));
    li.addEventListener("click", (e) => {
      if (e.ctrlKey || e.metaKey) {
        if (state.selectedRoster.has(idx)) state.selectedRoster.delete(idx);
        else state.selectedRoster.add(idx);
      } else {
        state.selectedRoster.clear();
        state.selectedRoster.add(idx);
      }
      renderRoster();
    });
    list.appendChild(li);
  });
  $("emptyState").classList.toggle("hidden", state.roster.length > 0);
}

function refreshUI() {
  renderRoster();
  $("artisansPrize").checked = state.artisansPrizeOwned;
  $("includeAnniversary").checked = state.includeAnniversary;
  const useOv = $("useWeightOverrides");
  if (useOv) useOv.checked = state.useWeightOverrides;
  $("outputPath").value = state.outputDir || "";
  const n = state.roster.length;
  const single = n === 1;
  const servers = new Set(state.roster.map((e) => (e.server || "").toLowerCase()).filter(Boolean));
  if (!state.generating) {
    let status = "Ready • No files loaded";
    if (n) {
      const serverNote = servers.size > 1 ? ` • ${servers.size} servers` : "";
      status = `Ready • ${n} character${n === 1 ? "" : "s"}${serverNote}`;
    }
    $("status").textContent = status;
    $("status").classList.toggle("ok", n > 0);
  }
  $("btnGenerate").disabled = state.generating || n === 0;
  syncOutputFormatChips();
  syncOptionsTabs(single);
}

function formatElapsed(seconds) {
  const s = Number(seconds);
  if (!Number.isFinite(s) || s < 0) return "";
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const rem = Math.round(s % 60);
  return `${m}m ${String(rem).padStart(2, "0")}s`;
}

function showGenProgress(fraction, message) {
  const wrap = $("genProgress");
  const bar = $("genProgressBar");
  if (!wrap || !bar) return;
  const pct = Math.max(0, Math.min(100, Math.round((Number(fraction) || 0) * 1000) / 10));
  wrap.classList.remove("hidden");
  wrap.setAttribute("aria-hidden", "false");
  wrap.setAttribute("aria-valuenow", String(Math.round(pct)));
  bar.style.width = `${pct}%`;
  if (message) {
    $("status").textContent = message;
    $("status").classList.remove("ok");
  }
}

function hideGenProgress() {
  const wrap = $("genProgress");
  const bar = $("genProgressBar");
  if (wrap) {
    wrap.classList.add("hidden");
    wrap.setAttribute("aria-hidden", "true");
    wrap.setAttribute("aria-valuenow", "0");
  }
  if (bar) bar.style.width = "0%";
}

function setOptionsTab(tab) {
  const single = state.roster.length === 1;
  if (tab === "advanced" && !single) tab = "options";
  state.optionsTab = tab;
  syncOptionsTabs(single);
  if (tab === "advanced") ensureWeightDefaultsLoaded();
}

function syncOptionsTabs(single) {
  const tabOptions = $("tabAugOptions");
  const tabAdvanced = $("tabAdvancedWeights");
  const paneOptions = $("paneAugOptions");
  const paneAdvanced = $("paneAdvancedWeights");
  const hint = $("advancedWeightsHint");
  if (!tabOptions || !tabAdvanced || !paneOptions || !paneAdvanced) return;

  if (!single && state.optionsTab === "advanced") {
    state.optionsTab = "options";
    state.useWeightOverrides = false;
    state.weightDefaults = null;
    state.weightEdits = null;
    state.weightsClassKey = null;
  }

  tabAdvanced.disabled = !single || state.generating;
  const useOv = $("useWeightOverrides");
  if (useOv) {
    useOv.disabled = !single || state.generating;
    useOv.checked = state.useWeightOverrides && single;
  }
  const resetBtn = $("btnResetWeights");
  if (resetBtn) {
    resetBtn.disabled =
      !single || state.generating || !state.useWeightOverrides;
  }
  const onAdvanced = state.optionsTab === "advanced" && single;
  tabOptions.classList.toggle("on", !onAdvanced);
  tabAdvanced.classList.toggle("on", onAdvanced);
  tabOptions.setAttribute("aria-selected", String(!onAdvanced));
  tabAdvanced.setAttribute("aria-selected", String(onAdvanced));
  paneOptions.classList.toggle("hidden", onAdvanced);
  paneAdvanced.classList.toggle("hidden", !onAdvanced);

  if (hint) {
    hint.textContent = single
      ? "Edit class default scoring weights for this generate only."
      : "Available with exactly one character on the roster.";
  }
  if (onAdvanced) ensureWeightDefaultsLoaded();
}

async function ensureWeightDefaultsLoaded() {
  if (state.optionsTab !== "advanced" || state.roster.length !== 1) return;
  const entry = state.roster[0];
  const classKey = entry.classAbbr || "";
  if (state.weightsClassKey === classKey && state.weightDefaults && state.weightEdits) {
    renderWeightGrid();
    return;
  }
  try {
    const info = await api("get_class_weight_defaults", classKey || null, state.profile);
    state.weightDefaults = info;
    state.weightEdits = { ...(info.weights || {}) };
    state.weightsClassKey = classKey;
    renderWeightGrid();
  } catch (err) {
    showToast(String(err.message || err), true);
  }
}

function renderWeightGrid() {
  const grid = $("weightGrid");
  const meta = $("advancedWeightsMeta");
  if (!grid || !meta) return;
  const info = state.weightDefaults;
  if (!info) {
    meta.textContent = "Loading defaults…";
    grid.innerHTML = "";
    return;
  }
  const cls = info.classAbbr || "unknown";
  const role = info.role || "—";
  meta.innerHTML = `Profile: <strong>${escapeHtml(info.profileLabel || info.profile)}</strong>
    · Class: <strong>${escapeHtml(cls)}</strong>
    · Role: <strong>${escapeHtml(role)}</strong>`;

  const labels = info.labels || {};
  const edits = state.weightEdits || {};
  const keys = Object.keys(info.weights || {});
  grid.innerHTML = "";
  keys.forEach((key) => {
    const row = document.createElement("label");
    row.className = "weight-row";
    const label = labels[key] || key;
    const val = edits[key] != null ? edits[key] : 0;
    row.innerHTML = `<span title="${escapeAttr(key)}">${escapeHtml(label)}</span>
      <input type="number" step="0.1" data-stat="${escapeAttr(key)}" value="${escapeAttr(val)}">`;
    const input = row.querySelector("input");
    input.disabled = !state.useWeightOverrides || state.generating;
    input.addEventListener("change", () => {
      const n = Number(input.value);
      if (!Number.isFinite(n)) return;
      state.weightEdits = state.weightEdits || {};
      state.weightEdits[key] = n;
    });
    grid.appendChild(row);
  });
}

async function resetWeightDefaults() {
  if (state.optionsTab !== "advanced" || state.roster.length !== 1) return;
  state.weightsClassKey = null;
  await ensureWeightDefaultsLoaded();
  const status = $("advancedResetStatus");
  if (!status) return;
  status.textContent = "Weights reset to class defaults";
  status.classList.add("on");
  clearTimeout(resetWeightDefaults._timer);
  resetWeightDefaults._timer = setTimeout(() => {
    status.classList.remove("on");
  }, 2200);
}

async function browseFolder() {
  try {
    const folder = await api("pick_folder");
    if (!folder) return;
    const data = await api("discover_folder_choices", folder);
    if (!data.choices || !data.choices.length) {
      showToast(`No inventory dumps found in:\n${folder}`, true);
      return;
    }
    showFolderPicker(data);
  } catch (err) {
    showToast(String(err.message || err), true);
  }
}

function showFolderPicker(data) {
  const serverOptions = ['<option value="">All servers</option>']
    .concat(
      (data.servers || []).map(
        (s) =>
          `<option value="${escapeAttr(s.slug)}">${escapeHtml(s.label)} (${escapeHtml(s.slug)})</option>`
      )
    )
    .join("");

  const rows = data.choices
    .map(
      (c, i) => `
    <label class="picker-item" data-server="${escapeAttr(c.server)}" data-index="${i}">
      <input type="checkbox" checked data-index="${i}">
      <div class="picker-body">
        <div class="char-card-host" data-choice-index="${i}"></div>
        ${c.summary ? `<div class="picker-summary">${escapeHtml(c.summary)}</div>` : ""}
      </div>
    </label>`
    )
    .join("");

  showModal(`
    <div class="modal wide">
      <div class="modal-header">
        <h2>Characters in folder</h2>
        <div class="path">${escapeHtml(data.folder)}</div>
        <p style="margin:8px 0 0;font-size:12px;color:var(--muted)">
          Choose which characters to add. You can add from multiple folders or servers.
        </p>
      </div>
      <div class="modal-body">
        <div class="picker-filter">
          <div class="field-label">Server</div>
          <select id="pickerServer">${serverOptions}</select>
        </div>
        <div class="field-label">Characters</div>
        <div class="picker-list" id="pickerList">${rows}</div>
        <div class="toolbar" style="margin-top:10px">
          <button type="button" class="btn btn-secondary" id="pickerAll">Select all</button>
          <button type="button" class="btn btn-secondary" id="pickerNone">Select none</button>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" id="pickerCancel">Cancel</button>
        <button type="button" class="btn btn-primary" id="pickerAdd">Add selected</button>
      </div>
    </div>`);

  data.choices.forEach((c, i) => {
    const host = document.querySelector(`.char-card-host[data-choice-index="${i}"]`);
    if (!host) return;
    // In picker, always show server so multi-server folders are clear
    host.appendChild(createCharCard(c, { showServer: true }));
  });

  const visiblePickerItems = () =>
    Array.from(document.querySelectorAll(".picker-item:not(.hidden-row)"));

  const filterRows = () => {
    const slug = $("pickerServer").value;
    document.querySelectorAll(".picker-item").forEach((row) => {
      const match = !slug || row.dataset.server.toLowerCase() === slug.toLowerCase();
      row.classList.toggle("hidden-row", !match);
    });
  };
  $("pickerServer").addEventListener("change", filterRows);

  $("pickerAll").addEventListener("click", () => {
    visiblePickerItems().forEach((row) => {
      row.querySelector("input").checked = true;
    });
  });
  $("pickerNone").addEventListener("click", () => {
    visiblePickerItems().forEach((row) => {
      row.querySelector("input").checked = false;
    });
  });
  $("pickerCancel").addEventListener("click", closeModal);
  $("pickerAdd").addEventListener("click", async () => {
    const selected = [];
    visiblePickerItems().forEach((row) => {
      const cb = row.querySelector("input");
      if (!cb || !cb.checked) return;
      const idx = Number(cb.dataset.index);
      selected.push(data.choices[idx]);
    });
    if (!selected.length) {
      showToast("Select at least one character.", true);
      return;
    }
    const newPaths = [];
    selected.forEach((c) => {
      (c.paths || [c.path]).forEach((p) => newPaths.push(p));
    });
    await addPaths(newPaths);
    closeModal();
  });
}

async function addPaths(paths) {
  let added = 0;
  for (const raw of paths) {
    if (!state.filePaths.includes(raw)) {
      state.filePaths.push(raw);
      added += 1;
    }
  }
  if (!added) {
    showToast("Those characters are already in the list.");
    return;
  }
  state.filePaths.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
  await rebuildRoster();
  try {
    const inferred = await api("infer_profile", state.filePaths);
    if (inferred && inferred.profile) state.profile = inferred.profile;
  } catch (_) {}
  refreshUI();
  showToast(`Added ${added} character${added === 1 ? "" : "s"}`);
}

async function rebuildRoster() {
  if (!state.filePaths.length) {
    state.roster = [];
    return;
  }
  state.roster = await api("build_roster", state.filePaths);
  // Keep selected indices valid
  const max = state.roster.length;
  state.selectedRoster = new Set([...state.selectedRoster].filter((i) => i >= 0 && i < max));
}

async function moveRoster(delta) {
  if (state.selectedRoster.size !== 1) return;
  const index = [...state.selectedRoster][0];
  const newIndex = index + delta;
  if (newIndex < 0 || newIndex >= state.roster.length) return;
  const tmp = state.roster[index];
  state.roster[index] = state.roster[newIndex];
  state.roster[newIndex] = tmp;
  // Keep filePaths aligned with roster order for generate
  state.filePaths = state.roster.map((e) => e.path);
  state.selectedRoster.clear();
  state.selectedRoster.add(newIndex);
  try {
    await api("save_roster_order", state.roster.map((e) => e.personaKey));
  } catch (_) {}
  refreshUI();
}

async function removeSelected() {
  if (!state.selectedRoster.size) return;
  const removing = [...state.selectedRoster].map((i) => state.roster[i]);
  const removingKeys = removing.map((e) => e.personaKey);
  let dropPaths = removing.map((e) => e.path);
  try {
    dropPaths = await api("paths_for_removal", removingKeys, state.roster, state.filePaths);
  } catch (_) {}
  const drop = new Set(dropPaths);
  state.filePaths = state.filePaths.filter((p) => !drop.has(p));
  state.selectedRoster.clear();
  await rebuildRoster();
  refreshUI();
}

async function clearFiles() {
  if (!state.filePaths.length) return;
  if (!confirm("Remove all characters from the list?")) return;
  state.filePaths = [];
  state.roster = [];
  state.selectedRoster.clear();
  try {
    await api("clear_files");
  } catch (_) {}
  refreshUI();
}

async function browseOutput() {
  try {
    const result = await api("pick_output_dir");
    if (!result || result.cancelled) return;
    if (result.ok && result.outputDir) {
      state.outputDir = result.outputDir;
      refreshUI();
    }
  } catch (e) {
    showToast(String(e.message || e), true);
  }
}

async function setOutputFormat(format) {
  if (!OUTPUT_FORMATS.includes(format)) return;
  state.outputFormat = format;
  syncOutputFormatChips();
  try {
    await api("set_output_format", format);
  } catch (_) {}
}

async function generate() {
  if (state.generating || !state.roster.length) return;
  // Sync paths to current roster order
  state.filePaths = state.roster.map((e) => e.path);
  state.generating = true;
  refreshUI();
  showGenProgress(0, "Fetching raidloot catalog and building report…");
  try {
    const useAdvanced =
      state.roster.length === 1 &&
      state.useWeightOverrides &&
      state.weightEdits &&
      Object.keys(state.weightEdits).length > 0;
    const result = await api("generate_report", {
      profile: state.profile,
      artisansPrizeOwned: state.artisansPrizeOwned,
      includeAnniversary: state.includeAnniversary,
      advancedWeights: !!useAdvanced,
      sessionWeights: useAdvanced ? { ...(state.weightEdits || {}) } : null,
      outputFormat: state.outputFormat,
      outputDir: state.outputDir,
      filePaths: state.filePaths,
      personaOrder: state.roster.map((e) => e.personaKey),
    });
    if (!result || !result.ok) {
      state.generating = false;
      hideGenProgress();
      refreshUI();
      showToast((result && result.error) || "Generate failed", true);
    }
  } catch (e) {
    state.generating = false;
    hideGenProgress();
    refreshUI();
    showToast(String(e.message || e), true);
  }
}

window.onGenerateProgress = function (payload) {
  if (!payload) return;
  showGenProgress(payload.fraction, payload.message);
};

window.onGenerateComplete = function (result) {
  state.generating = false;
  hideGenProgress();
  refreshUI();
  if (!result || !result.ok) {
    showToast((result && result.error) || "Generate failed", true);
    $("status").textContent = "Error";
    $("status").classList.remove("ok");
    return;
  }
  const parts = [];
  if (result.xlsx) parts.push(result.xlsx);
  if (result.html) parts.push(result.html);
  const elapsed = formatElapsed(result.elapsedSeconds);
  $("status").textContent = elapsed
    ? `Done • ${result.characterCount} character(s) • ${elapsed}`
    : `Done • ${result.characterCount} character(s)`;
  $("status").classList.add("ok");
  let msg = `Report saved${result.fromCache ? " (used cached raidloot data)" : ""}`;
  if (parts.length) msg += `\n${parts.join("\n")}`;
  if (result.warnings && result.warnings.length) {
    msg += `\n${result.warnings.join("\n")}`;
  }
  showToast(msg);
};

let eventsBound = false;

function bindEvents() {
  if (eventsBound) return;
  eventsBound = true;

  $("helpBtn").addEventListener("click", (e) => {
    e.stopPropagation();
    $("helpMenu").classList.toggle("hidden");
  });
  document.addEventListener("click", () => $("helpMenu").classList.add("hidden"));
  $("helpMenu").addEventListener("click", (e) => e.stopPropagation());

  $("helpAbout").addEventListener("click", async () => {
    $("helpMenu").classList.add("hidden");
    let ver = "";
    try {
      const info = await api("get_version");
      ver = info.version;
    } catch (_) {}
    showModal(`
      <div class="modal">
        <div class="modal-header"><h2>About EQ Augs</h2></div>
        <div class="modal-body">
          <p>Version ${ver}</p>
          <p style="margin-top:12px;color:var(--muted);font-size:12px">
            Compares equipped Slot2 type 7/8 augs from EverQuest inventory dumps
            against live raidloot.com rankings. Stat focus (Dex / INT / WIS) is
            detected from Chest armor class. Options cover Artisan's Prize ownership
            and whether anniversary Distant Echoes gems are included.
            Select characters from one or more folders/servers, then reorder columns
            with Up/Down.
          </p>
        </div>
        <div class="modal-footer"><button type="button" class="btn" id="modalClose">Close</button></div>
      </div>`);
    $("modalClose").addEventListener("click", closeModal);
  });

  $("btnFolder").addEventListener("click", browseFolder);
  $("btnBrowse").addEventListener("click", browseOutput);
  $("btnUp").addEventListener("click", () => moveRoster(-1));
  $("btnDown").addEventListener("click", () => moveRoster(1));
  $("btnRemove").addEventListener("click", removeSelected);
  $("btnClear").addEventListener("click", clearFiles);
  $("btnGenerate").addEventListener("click", generate);

  $("artisansPrize").addEventListener("change", async () => {
    state.artisansPrizeOwned = $("artisansPrize").checked;
    try {
      await api("set_artisans_prize", state.artisansPrizeOwned);
    } catch (_) {}
  });
  $("includeAnniversary").addEventListener("change", async () => {
    state.includeAnniversary = $("includeAnniversary").checked;
    try {
      await api("set_include_anniversary", state.includeAnniversary);
    } catch (_) {}
  });
  $("tabAugOptions").addEventListener("click", () => setOptionsTab("options"));
  $("tabAdvancedWeights").addEventListener("click", () => {
    if (state.roster.length !== 1) {
      showToast("Advanced weights need a single character.", true);
      return;
    }
    setOptionsTab("advanced");
  });
  $("useWeightOverrides").addEventListener("change", () => {
    state.useWeightOverrides =
      $("useWeightOverrides").checked && state.roster.length === 1;
    const resetBtn = $("btnResetWeights");
    if (resetBtn) {
      resetBtn.disabled =
        state.roster.length !== 1 ||
        state.generating ||
        !state.useWeightOverrides;
    }
    renderWeightGrid();
  });
  $("btnResetWeights").addEventListener("click", () => {
    resetWeightDefaults();
  });

  OUTPUT_FORMATS.forEach((fmt) => {
    const chip = $(`chipFormat${fmt[0].toUpperCase()}${fmt.slice(1)}`);
    if (chip) chip.addEventListener("click", () => setOutputFormat(fmt));
  });
}

async function initApp() {
  bindEvents();
  refreshUI();
  if (!window.pywebview || !pywebview.api) return;
  try {
    const info = await api("get_version");
    $("versionBadge").textContent = `v${info.version}`;
    if (info.logoDataUri) $("logo").src = info.logoDataUri;
  } catch (_) {}
  try {
    const prefs = await api("get_gui_prefs");
    if (prefs.profile) state.profile = prefs.profile;
    if (typeof prefs.artisansPrizeOwned === "boolean") {
      state.artisansPrizeOwned = prefs.artisansPrizeOwned;
    }
    if (typeof prefs.includeAnniversary === "boolean") {
      state.includeAnniversary = prefs.includeAnniversary;
    }
    if (prefs.outputFormat) state.outputFormat = prefs.outputFormat;
    if (prefs.outputDir) state.outputDir = prefs.outputDir;
    refreshUI();
  } catch (_) {}
}

window.addEventListener("pywebviewready", initApp);
if (window.pywebview && pywebview.api) initApp();
else
  document.addEventListener("DOMContentLoaded", () => {
    bindEvents();
    refreshUI();
  });
