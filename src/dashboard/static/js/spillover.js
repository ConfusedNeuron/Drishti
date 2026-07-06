let _studyLoaded = false;
let _labCatalog = null;
let _labSeries = []; // [{id, label}]

async function loadDY() {
  document.getElementById("dy-spinner").style.display = "block";
  try {
    const r = await fetch(window.API + "/api/research/spillover");
    if (!r.ok) { document.getElementById("dy-total").textContent = "Spillover unavailable"; return; }
    const d = await r.json();
    document.getElementById("dy-total").textContent =
      `Total Connectedness: ${d.total_connectedness.toFixed(1)}%`;
    const names = Object.keys(d.to_spillover);
    Plotly.newPlot("dy-chart", [
      { type: "bar", name: "To (transmitting)", x: names, y: names.map(n => d.to_spillover[n]),
        marker: { color: COLORS.gold } },
      { type: "bar", name: "From (receiving)",  x: names, y: names.map(n => d.from_spillover[n]),
        marker: { color: COLORS.teal } },
    ], {
      ...CL, barmode: "group",
      margin: { t: 10, b: 80, l: 60, r: 16 },
      yaxis: { ...CL.yaxis, title: { text: "Spillover (%)", font: { size: 10 } } },
      legend: { orientation: "h", y: -0.28, font: { size: 10 } },
    }, CONF);
  } finally {
    document.getElementById("dy-spinner").style.display = "none";
  }
  // Load universe study once, in parallel with the existing per-index chart
  if (!_studyLoaded) { _studyLoaded = true; loadSpilloverStudy(); }
}

async function loadRollingSpillover() {
  const spinner = document.getElementById("rolling-dy-spinner");
  const chartEl = document.getElementById("rolling-dy-chart");
  if (!spinner || !chartEl) return;
  spinner.style.display = "block";
  try {
    const r = await fetch(window.API + "/api/research/spillover/rolling");
    if (!r.ok) { chartEl.textContent = "Rolling spillover unavailable"; return; }
    const d = await r.json();
    Plotly.newPlot("rolling-dy-chart", [{
      type: "scatter",
      mode: "lines",
      name: "Total Connectedness",
      x: d.dates,
      y: d.values,
      line: { color: COLORS.gold, width: 1.8 },
      fill: "tozeroy",
      fillcolor: "rgba(201,162,39,0.08)",
      hovertemplate: "%{x}<br>Connectedness: %{y:.1f}%<extra></extra>",
    }], {
      ...CL,
      margin: { t: 10, b: 60, l: 60, r: 16 },
      yaxis: { ...CL.yaxis, title: { text: "Connectedness (%)", font: { size: 10 } }, rangemode: "tozero" },
      xaxis: { ...CL.xaxis, type: "date" },
    }, CONF);
    document.getElementById("rolling-dy-note").textContent =
      `${d.note} Window: ${d.window}d, step: ${d.step}d.`;
  } finally {
    spinner.style.display = "none";
  }
}

async function loadDCC() {
  document.getElementById("dcc-spinner").style.display = "block";
  try {
    const r = await fetch(window.API + "/api/research/dcc");
    if (!r.ok) { document.getElementById("dcc-chart").textContent = "DCC unavailable"; return; }
    const d = await r.json();
    const dccColors = [COLORS.gold, COLORS.teal, COLORS.orange, COLORS.ok, COLORS.danger, "#8B68D8"];
    const traces = Object.entries(d.time_varying_correlations).map(([pair, series], i) => ({
      type: "scatter", mode: "lines", name: pair.replace(/_/g, " → "),
      x: series.dates, y: series.values,
      line: { color: dccColors[i % dccColors.length], width: 1.5 },
    }));
    Plotly.newPlot("dcc-chart", traces, {
      ...CL,
      margin: { t: 10, b: 60, l: 60, r: 16 },
      yaxis: { ...CL.yaxis, title: { text: "Conditional Correlation", font: { size: 10 } } },
      xaxis: { ...CL.xaxis, type: "date" },
      legend: { orientation: "h", y: -0.25, font: { size: 10 } },
    }, CONF);
  } finally {
    document.getElementById("dcc-spinner").style.display = "none";
  }
}

async function loadSpilloverStudy() {
  const spinner = document.getElementById("study-spinner");
  if (spinner) spinner.style.display = "block";
  try {
    const r = await fetch(window.API + "/api/research/spillover/study");
    if (!r.ok) {
      if (spinner) spinner.textContent = "Universe spillover study unavailable";
      return;
    }
    const d = await r.json();

    // KPI cards: prefer in_sample.total_spillover, fall back to panel-level total_spillover
    const kpiFor = (key) => {
      const p = d.panels[key];
      if (!p) return "n/a";
      const val = (p.in_sample && p.in_sample.total_spillover != null)
        ? p.in_sample.total_spillover
        : p.total_spillover;
      return val != null ? val.toFixed(1) + "%" : "n/a";
    };
    document.getElementById("study-kpi-large").textContent    = kpiFor("large");
    document.getElementById("study-kpi-mid").textContent      = kpiFor("mid");
    document.getElementById("study-kpi-combined").textContent = kpiFor("combined");

    // Rolling connectedness — three traces from top-level rolling object
    const cohortColors = { large: COLORS.gold, mid: COLORS.teal, combined: COLORS.ok };
    const rollingTraces = Object.entries(d.rolling || {}).map(([cohort, dateMap]) => {
      const dates = Object.keys(dateMap).sort();
      return {
        type: "scatter", mode: "lines",
        name: cohort.charAt(0).toUpperCase() + cohort.slice(1),
        x: dates,
        y: dates.map(dt => dateMap[dt]),
        line: { color: cohortColors[cohort] || COLORS.gold, width: 1.8 },
        hovertemplate: "%{x}<br>" + cohort + ": %{y:.1f}%<extra></extra>",
      };
    });
    if (rollingTraces.length) {
      Plotly.newPlot("study-rolling-chart", rollingTraces, {
        ...CL,
        margin: { t: 10, b: 60, l: 60, r: 16 },
        yaxis: { ...CL.yaxis, title: { text: "Connectedness (%)", font: { size: 10 } }, rangemode: "tozero" },
        xaxis: { ...CL.xaxis, type: "date" },
        legend: { orientation: "h", y: -0.25, font: { size: 10 } },
      }, CONF);
    }

    // Net spillover bar chart — combined panel, sorted descending
    const combined = d.panels && d.panels.combined;
    const netMap = combined && combined.net_spillover;
    if (netMap) {
      const entries = Object.entries(netMap).sort((a, b) => b[1] - a[1]);
      const sectors = entries.map(e => e[0]);
      const vals    = entries.map(e => e[1]);
      const barColors = vals.map(v => v >= 0 ? COLORS.ok : COLORS.danger);
      Plotly.newPlot("study-net-chart", [{
        type: "bar",
        x: vals,
        y: sectors,
        orientation: "h",
        marker: { color: barColors },
        hovertemplate: "%{y}<br>Net: %{x:.1f}%<extra></extra>",
      }], {
        ...CL,
        margin: { t: 10, b: 40, l: 160, r: 40 },
        xaxis: { ...CL.xaxis, title: { text: "Net Spillover (%)", font: { size: 10 } }, zeroline: true, zerolinecolor: "var(--line-2)" },
        yaxis: { ...CL.yaxis, autorange: "reversed" },
      }, CONF);
    }
  } finally {
    if (spinner) spinner.style.display = "none";
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Spillover Lab — user-driven Diebold-Yilmaz on any 3-12 cached series.
// Educational/diagnostic only, no investment-advice language.
// ─────────────────────────────────────────────────────────────────────────

function showLabError(msg) {
  const el = document.getElementById("lab-error");
  if (!el) return;
  el.textContent = msg;
  el.style.display = "block";
}

function hideLabError() {
  const el = document.getElementById("lab-error");
  if (el) el.style.display = "none";
}

async function loadSpilloverCatalog() {
  try {
    const r = await fetch(window.API + "/api/research/spillover/catalog");
    if (!r.ok) {
      showLabError("Spillover Lab catalog unavailable — series picker is disabled.");
      return;
    }
    _labCatalog = await r.json();
    onLabCategoryChange();
  } catch (e) {
    showLabError("Spillover Lab catalog unavailable — series picker is disabled.");
  }
}

function onLabCategoryChange() {
  if (!_labCatalog) return;
  const cat = document.getElementById("lab-category").value;
  const dl = document.getElementById("lab-series-dl");
  const entries = _labCatalog[cat] || [];
  dl.innerHTML = entries.map(e => `<option value="${esc(e.label)}">`).join("");
}

function addLabSeries() {
  hideLabError();
  const input = document.getElementById("lab-series-input");
  const label = input.value.trim();
  if (!label || !_labCatalog) return;

  const cat = document.getElementById("lab-category").value;
  const entries = _labCatalog[cat] || [];
  const match = entries.find(e => e.label === label);
  if (!match) return; // not a recognized catalog entry — ignore (datalist-constrained input)
  if (_labSeries.some(s => s.id === match.id)) { input.value = ""; return; }
  if (_labSeries.length >= 12) {
    showLabError("Cap is 12 series — remove one before adding another.");
    return;
  }

  _labSeries.push(match);
  renderLabChips();
  input.value = "";
}

function removeLabSeries(id) {
  _labSeries = _labSeries.filter(s => s.id !== id);
  renderLabChips();
}

function renderLabChips() {
  const el = document.getElementById("lab-chips");
  el.innerHTML = _labSeries
    .map(s => `<span class="chip">${esc(s.label)}<span class="x" onclick="removeLabSeries('${s.id}')">✕</span></span>`)
    .join("");
  const n = _labSeries.length;
  document.getElementById("lab-count").textContent = `${n}/12 selected`;
  document.getElementById("lab-run").disabled = !(n >= 3 && n <= 12);
}

async function runSpilloverLab() {
  const runBtn = document.getElementById("lab-run");
  const errEl = document.getElementById("lab-error");
  const resultsEl = document.getElementById("lab-results");
  const prevText = runBtn.textContent;
  runBtn.disabled = true;
  runBtn.textContent = "Running…";
  errEl.style.display = "none";

  try {
    const body = {
      series: _labSeries.map(s => s.id),
      start: document.getElementById("lab-start").value || null,
      end: document.getElementById("lab-end").value || null,
      fevd_horizon: parseInt(document.getElementById("lab-horizon").value, 10),
      rolling: document.getElementById("lab-rolling").checked,
      window: parseInt(document.getElementById("lab-window").value, 10),
      step: parseInt(document.getElementById("lab-step").value, 10),
    };

    const r = await fetch(window.API + "/api/research/spillover/custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!r.ok) {
      let detail = "Spillover Lab computation failed.";
      try { detail = (await r.json()).detail || detail; } catch (e) {}
      errEl.textContent = detail;
      errEl.style.display = "block";
      resultsEl.style.display = "none";
      return;
    }

    const d = await r.json();
    renderLabResults(d);
    resultsEl.style.display = "block";
  } finally {
    runBtn.disabled = !(_labSeries.length >= 3 && _labSeries.length <= 12);
    runBtn.textContent = prevText;
  }
}

function renderLabResults(d) {
  document.getElementById("lab-total").textContent =
    `Total Connectedness: ${d.total_connectedness.toFixed(1)}%`;

  // Net-spillover horizontal bar — mirrors the study-net-chart pattern above.
  const netEntries = Object.entries(d.net_spillover).sort((a, b) => b[1] - a[1]);
  const netLabels = netEntries.map(e => e[0]);
  const netVals   = netEntries.map(e => e[1]);
  const barColors = netVals.map(v => v >= 0 ? COLORS.ok : COLORS.danger);
  Plotly.newPlot("lab-net-chart", [{
    type: "bar",
    x: netVals,
    y: netLabels,
    orientation: "h",
    marker: { color: barColors },
    hovertemplate: "%{y}<br>Net: %{x:.1f}%<extra></extra>",
  }], {
    ...CL,
    margin: { t: 10, b: 40, l: 160, r: 40 },
    xaxis: { ...CL.xaxis, title: { text: "Net Spillover (%)", font: { size: 10 } }, zeroline: true, zerolinecolor: "var(--line-2)" },
    yaxis: { ...CL.yaxis, autorange: "reversed" },
  }, CONF);

  // Pairwise heatmap — d.pairwise is a dict-of-dicts, outer keys = rows, inner = cols.
  const rows = Object.keys(d.pairwise);
  const cols = rows.length ? Object.keys(d.pairwise[rows[0]]) : [];
  const z = rows.map(row => cols.map(col => d.pairwise[row][col]));
  Plotly.newPlot("lab-heatmap", [{
    type: "heatmap",
    z, x: cols, y: rows,
    colorscale: "YlOrRd",
    hovertemplate: "%{y} ← %{x}<br>%{z:.1f}%<extra></extra>",
  }], {
    ...CL,
    margin: { t: 10, b: 90, l: 110, r: 16 },
    xaxis: { ...CL.xaxis, tickfont: { size: 9 } },
    yaxis: { ...CL.yaxis, tickfont: { size: 9 } },
  }, CONF);

  // Rolling connectedness — only when the backend returned it (data long enough).
  const rollingWrap = document.getElementById("lab-rolling-wrap");
  if (d.rolling) {
    Plotly.newPlot("lab-rolling-chart", [{
      type: "scatter",
      mode: "lines",
      name: "Total Connectedness",
      x: d.rolling.dates,
      y: d.rolling.values,
      line: { color: COLORS.gold, width: 1.8 },
      fill: "tozeroy",
      fillcolor: "rgba(201,162,39,0.08)",
      hovertemplate: "%{x}<br>Connectedness: %{y:.1f}%<extra></extra>",
    }], {
      ...CL,
      margin: { t: 10, b: 60, l: 60, r: 16 },
      yaxis: { ...CL.yaxis, title: { text: "Connectedness (%)", font: { size: 10 } }, rangemode: "tozero" },
      xaxis: { ...CL.xaxis, type: "date" },
    }, CONF);
    rollingWrap.style.display = "block";
  } else {
    rollingWrap.style.display = "none";
  }

  const m = d.meta;
  document.getElementById("lab-meta").textContent =
    `n_obs ${m.n_obs} · ${m.start}→${m.end} · VAR lag ${d.var_lag} · ${m.n_series} series` +
    (m.dropped_note ? ` · ${m.dropped_note}` : "");
}
