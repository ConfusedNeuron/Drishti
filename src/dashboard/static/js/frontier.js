let frontierData = null;
let _frontierHorizon = "1y";
let _frontierCands = [];
let _frontierPoint = "tangency";

async function loadFrontierUniverse() {
  try {
    const r = await fetch(window.API + "/api/frontier/universe");
    if (!r.ok) {
      document.getElementById("frontier-meta").textContent =
        "Universe list unavailable — you can still run on holdings only.";
      return;
    }
    const d = await r.json();
    const dl = document.getElementById("frontier-universe-dl");
    dl.innerHTML = d.candidates
      .map(c => `<option value="${c.symbol}">${c.sector}</option>`)
      .join("");
  } catch (e) {
    document.getElementById("frontier-meta").textContent =
      "Universe list unavailable — you can still run on holdings only.";
  }
}

function selectFrontierHorizon(btn) {
  _frontierHorizon = btn.dataset.horizon;
  document.querySelectorAll("#frontier-horizons button").forEach(b => b.classList.remove("pill-active"));
  btn.classList.add("pill-active");
}

function addFrontierCandidate() {
  const input = document.getElementById("frontier-cand-input");
  let sym = input.value.trim().toUpperCase().replace(/[^A-Z0-9&._-]/g, "");
  if (!sym) return;
  if (_frontierCands.some(c => c.toUpperCase() === sym)) { input.value = ""; return; }
  if (_frontierCands.length >= 15) { alert("Candidate cap is 15"); return; }
  _frontierCands.push(sym);
  renderFrontierChips();
  input.value = "";
}

function removeFrontierCandidate(sym) {
  _frontierCands = _frontierCands.filter(c => c !== sym);
  renderFrontierChips();
}

function renderFrontierChips() {
  const el = document.getElementById("frontier-chips");
  el.innerHTML = _frontierCands
    .map(sym => `<span class="chip">${sym}<span class="x" onclick="removeFrontierCandidate('${sym}')">✕</span></span>`)
    .join("");
}

async function runFrontier(point) {
  _frontierPoint = point || _frontierPoint;

  const runBtn = document.getElementById("frontier-run");
  const spinner = document.getElementById("frontier-spinner");
  const errEl = document.getElementById("frontier-error");
  runBtn.disabled = true;
  runBtn.textContent = "Running…";
  spinner.style.display = "block";
  errEl.style.display = "none";

  try {
    const r = await fetch(window.API + "/api/frontier/compute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        horizon: _frontierHorizon,
        long_only: document.getElementById("frontier-longonly").checked,
        candidates: _frontierCands,
        point: _frontierPoint,
      }),
    });

    if (!r.ok) {
      let detail = "Frontier computation failed.";
      try { detail = (await r.json()).detail || detail; } catch (e) {}
      errEl.textContent = detail;
      errEl.style.display = "block";
      document.getElementById("frontier-chart-section").style.display = "none";
      document.getElementById("frontier-gap-section").style.display = "none";
      return;
    }

    frontierData = await r.json();
    document.getElementById("frontier-chart-section").style.display = "block";
    document.getElementById("frontier-gap-section").style.display = "block";

    const m = frontierData.meta;
    const shrinkage = (m.shrinkage != null) ? m.shrinkage.toFixed(3) : "n/a";
    let meta = `n_obs ${m.n_obs} · freq ${m.frequency} · assets ${m.n_assets} · shrinkage λ ${shrinkage} · ` +
      `rf ${(m.rf * 100).toFixed(2)}%${m.rf_fallback ? " (fallback)" : ""} · window ${m.window_start}→${m.window_end}`;
    if (m.dropped_symbols && m.dropped_symbols.length) meta += ` · dropped: ${m.dropped_symbols.join(", ")}`;
    if (m.unknown_candidates && m.unknown_candidates.length) meta += ` · unknown: ${m.unknown_candidates.join(", ")}`;
    document.getElementById("frontier-meta").textContent = meta;

    renderFrontierChart(frontierData);
    renderFrontierGap(frontierData);
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = "Run analysis";
    spinner.style.display = "none";
  }
}

function selectFrontierPoint(btn) {
  document.querySelectorAll("#frontier-point-btns button").forEach(b => b.classList.remove("pill-active"));
  btn.classList.add("pill-active");

  const kind = btn.dataset.point;
  let mapped = kind;
  if (kind === "conservative" || kind === "balanced" || kind === "aggressive") {
    if (!frontierData || !frontierData.presets) { _frontierPoint = kind; return; }
    const preset = frontierData.presets.find(p => p.label === kind);
    mapped = preset ? preset.vol : kind;
  }
  runFrontier(mapped);
}

// Task 5 renders the Plotly frontier/CML/current-position chart here
function renderFrontierChart(d) {}

// Task 5 renders the weight-gap table here
function renderFrontierGap(d) {}
