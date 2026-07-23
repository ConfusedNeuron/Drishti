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
  syncPointButtons(btn.dataset.point);

  const kind = btn.dataset.point;
  let mapped = kind;
  if (kind === "conservative" || kind === "balanced" || kind === "aggressive") {
    if (!frontierData || !frontierData.presets) { _frontierPoint = kind; return; }
    const preset = frontierData.presets.find(p => p.label === kind);
    mapped = preset ? preset.vol : kind;
  }
  runFrontier(mapped);
}

// Click handler is bound once because the #frontier-chart div persists across
// Plotly.newPlot() re-renders (newPlot reuses the existing DOM node) — binding
// on every render would stack duplicate "plotly_click" listeners.
let _frontierClickBound = false;

function syncPointButtons(kindOrLabel) {
  document.querySelectorAll("#frontier-point-btns button").forEach(b => {
    b.classList.toggle("pill-active", b.dataset.point === kindOrLabel);
  });
}

function renderFrontierChart(d) {
  const bandLo = {
    type: "scatter", mode: "lines",
    x: d.band.risk_lo, y: d.band.ret,
    line: { width: 0 }, hoverinfo: "skip", showlegend: false, name: "band-lo",
  };
  const bandHi = {
    type: "scatter", mode: "lines",
    x: d.band.risk_hi, y: d.band.ret,
    line: { width: 0 }, fill: "tonextx", fillcolor: "rgba(125,133,144,0.18)",
    name: "Bootstrap band (P10–P90)",
    hovertemplate: "vol %{x:.1%} · ret %{y:.1%}<extra>band</extra>",
  };
  const frontierLine = {
    type: "scatter", mode: "lines",
    x: d.frontier.risk, y: d.frontier.ret,
    line: { color: COLORS.gold, width: 2.2 },
    name: "Efficient frontier",
    hovertemplate: "vol %{x:.1%} · ret %{y:.1%}<extra>frontier</extra>",
  };

  const xMax = 1.2 * Math.max(...d.frontier.risk);
  const slope = (d.cml.ret - d.cml.rf) / d.cml.vol;
  const cml = {
    type: "scatter", mode: "lines",
    x: [0, xMax], y: [d.cml.rf, d.cml.rf + slope * xMax],
    line: { color: COLORS.muted, width: 1.4, dash: "dash" },
    name: "CML", hoverinfo: "skip",
  };

  const presetDots = {
    type: "scatter", mode: "markers+text",
    x: d.presets.map(p => p.vol), y: d.presets.map(p => p.ret),
    text: d.presets.map(p => p.label), textposition: "top center",
    textfont: { size: 9, color: COLORS.muted },
    marker: { size: 7, color: COLORS.palette[4] },
    customdata: d.presets.map(p => p.label),
    name: "Presets",
    hovertemplate: "%{customdata}<br>vol %{x:.1%} · ret %{y:.1%}<extra></extra>",
  };

  const minvarStar = {
    type: "scatter", mode: "markers",
    x: [d.minvar.vol], y: [d.minvar.ret],
    marker: { symbol: "star", size: 12, color: COLORS.palette[1] },
    name: "Min-variance",
    hovertemplate: "vol %{x:.1%} · ret %{y:.1%}<extra>min-variance</extra>",
  };

  const tangSharpe = (d.tangency.sharpe != null) ? d.tangency.sharpe.toFixed(2) : "n/a";
  const tangencyStar = {
    type: "scatter", mode: "markers",
    x: [d.tangency.vol], y: [d.tangency.ret],
    marker: { symbol: "star", size: 14, color: COLORS.ok },
    name: "Tangency (max Sharpe)",
    hovertemplate: `vol %{x:.1%} · ret %{y:.1%} · Sharpe ${tangSharpe}<extra>tangency</extra>`,
  };

  const traces = [bandLo, bandHi, frontierLine, cml, presetDots, minvarStar, tangencyStar];

  if (d.current.vol != null) {
    const cov = (d.current.coverage != null) ? (d.current.coverage * 100).toFixed(0) : "n/a";
    traces.push({
      type: "scatter", mode: "markers",
      x: [d.current.vol], y: [d.current.ret],
      marker: { symbol: "diamond", size: 12, color: COLORS.teal, line: { width: 1, color: COLORS.teal } },
      name: "Current portfolio",
      hovertemplate: `vol %{x:.1%} · ret %{y:.1%} · coverage ${cov}%<extra>current</extra>`,
    });
  }

  Plotly.newPlot("frontier-chart", traces, {
    ...CL,
    margin: { t: 10, b: 60, l: 64, r: 16 },
    xaxis: { ...CL.xaxis, type: "linear", title: { text: "Volatility (ann.)", font: { size: 10 } }, tickformat: ".0%", rangemode: "tozero" },
    yaxis: { ...CL.yaxis, type: "linear", title: { text: "Expected return (ann.)", font: { size: 10 } }, tickformat: ".0%" },
    legend: { orientation: "h", y: -0.22, font: { size: 10 } },
    hovermode: "closest",
  }, CONF);

  const el = document.getElementById("frontier-chart");
  if (!_frontierClickBound) {
    _frontierClickBound = true;
    el.on("plotly_click", (ev) => {
      const pt = ev.points[0];
      const name = pt.data.name;
      if (name === "Tangency (max Sharpe)") {
        syncPointButtons("tangency");
        runFrontier("tangency");
      } else if (name === "Min-variance") {
        syncPointButtons("minvar");
        runFrontier("minvar");
      } else if (name === "Efficient frontier" || name === "Presets") {
        const label = pt.customdata;
        if (name === "Presets" && label) {
          syncPointButtons(label);
        } else {
          syncPointButtons(null); // target_vol has no dedicated button — clear actives
        }
        runFrontier(pt.x);
      }
      // band/CML/current: ignored
    });
  }
}

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function renderFrontierGap(d) {
  const tableEl = document.getElementById("frontier-gap-table");
  const noteEl = document.getElementById("frontier-coverage-note");

  if (!d.gap || !d.gap.length) {
    tableEl.innerHTML = `<p class="chart-note">No weight differences above the 0.1% display threshold.</p>`;
  } else {
    const rows = d.gap.map(g => {
      const deltaPP = g.delta * 100;
      let color = "var(--muted)";
      if (Math.abs(g.delta) >= 0.0005) {
        color = deltaPP > 0 ? "var(--ok)" : "var(--danger)";
      }
      const sign = deltaPP > 0 ? "+" : "";
      return `<tr>
        <td>${esc(g.symbol)}</td>
        <td>${(g.current * 100).toFixed(2)}%</td>
        <td>${(g.target * 100).toFixed(2)}%</td>
        <td style="color:${color}">${sign}${deltaPP.toFixed(2)} pp</td>
      </tr>`;
    }).join("");

    tableEl.innerHTML = `
      <table class="data-table">
        <thead><tr><th>Symbol</th><th>Current %</th><th>Target %</th><th>Delta (pp)</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <p class="chart-note">${d.gap.length} symbols · selected point: ${esc(d.selected.kind)}</p>
    `;
  }

  if (d.current.coverage != null && d.current.coverage < 0.999) {
    const cov = (d.current.coverage * 100).toFixed(0);
    noteEl.textContent = `Note: only ${cov}% of current portfolio weight is covered by the estimation ` +
      `universe; the current-portfolio marker and gap table are computed on the covered subset.`;
    noteEl.style.display = "block";
  } else {
    noteEl.style.display = "none";
  }
}
