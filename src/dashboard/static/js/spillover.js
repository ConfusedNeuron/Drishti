let _studyLoaded = false;

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
