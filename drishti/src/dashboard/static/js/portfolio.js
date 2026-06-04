let riskData = null;
let _regimeLoaded = false;
let _icLoaded = false;
let _newsLoaded = false;
let _breachLoaded = false;

function showTab(name, btn) {
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll("nav button").forEach(b => b.classList.remove("active"));
  document.getElementById("tab-" + name).classList.add("active");
  btn.classList.add("active");

  if (name === "research") {
    if (!_newsLoaded)  { loadNews();  _newsLoaded  = true; }
    if (!_breachLoaded){ loadBreach(); _breachLoaded = true; }
    if (!_icLoaded)    loadIC();
  }
  if (name === "spillover") { loadDY(); loadDCC(); loadRollingSpillover(); }
  if (name === "risk") {
    if (riskData) renderRiskDetail(riskData);
    if (!_regimeLoaded) loadRegime();
  }
}

async function importSample() {
  const r = await fetch(window.API + "/api/portfolio/import/sample?sample_id=nifty-demo-2026", { method: "POST" });
  if (!r.ok) { alert("Sample import failed: " + (await r.text())); return; }
  document.getElementById("kpi-source").textContent = "Sample portfolio loaded";
  document.getElementById("run-btn").disabled = false;
}

async function importCSV(input) {
  const fd = new FormData();
  fd.append("file", input.files[0]);
  const r = await fetch(window.API + "/api/portfolio/import/csv", { method: "POST", body: fd });
  if (!r.ok) { alert("CSV import failed: " + (await r.text())); return; }
  document.getElementById("kpi-source").textContent = "CSV portfolio loaded";
  document.getElementById("run-btn").disabled = false;
}

async function runRisk() {
  const btn = document.getElementById("run-btn");
  btn.textContent = "Running…";
  btn.disabled = true;
  try {
    const r = await fetch(window.API + "/api/risk/summary?confidence=0.99&horizon_days=10", { method: "POST" });
    if (!r.ok) { const e = await r.json(); alert("Risk failed: " + e.detail); return; }
    riskData = await r.json();
    renderOverview(riskData);
    loadDrawdown();
  } finally {
    btn.textContent = "Run Risk Analysis";
    btn.disabled = false;
  }
}

function renderOverview(d) {
  document.getElementById("kpi-value").textContent = "₹" + fmt(d.portfolio_value);
  document.getElementById("kpi-var").textContent = "₹" + fmt(d.var.historical.amount);
  document.getElementById("kpi-es").textContent = "₹" + fmt(d.expected_shortfall.amount);

  const bt = d.backtest;
  if (bt.error) {
    document.getElementById("kpi-bt").textContent = "—";
    document.getElementById("kpi-bt-sub").textContent = bt.error;
  } else {
    const pass = bt.kupiec.pass_ && bt.christoffersen.pass_;
    document.getElementById("kpi-bt").innerHTML =
      `<span class="${pass ? 'pass' : 'fail'}">${pass ? "✓ Pass" : "⚠ Partial"}</span>`;
    document.getElementById("kpi-bt-sub").textContent =
      `${bt.violations} violations / ${bt.obs} obs`;
  }

  if (d.regime) {
    document.getElementById("regime-badge").innerHTML =
      `<span class="badge badge-${d.regime.label}">${d.regime.label.replace("_", "-")}</span>`;
  }

  const methods = Object.keys(d.var);
  Plotly.newPlot("var-chart", [{
    type: "bar",
    x: methods.map(m => m.replace("_", " ").replace(/\b\w/g, c => c.toUpperCase())),
    y: methods.map(m => d.var[m].amount),
    marker: { color: [COLORS.gold, COLORS.teal, COLORS.orange] },
    text: methods.map(m => "₹" + fmt(d.var[m].amount)),
    textposition: "outside",
    textfont: { color: COLORS.gold, size: 10, family: "'JetBrains Mono', monospace" },
  }], {
    ...CL,
    margin: { t: 24, b: 40, l: 70, r: 16 },
    yaxis: { ...CL.yaxis, title: { text: "VaR (₹)", font: { size: 10 } } },
  }, CONF);

  const contribs = d.top_contributors;
  Plotly.newPlot("contrib-chart", [{
    type: "pie",
    labels: contribs.map(c => c.symbol),
    values: contribs.map(c => Math.max(0, c.component_var)),
    textinfo: "label+percent",
    textfont: { size: 11, family: "'JetBrains Mono', monospace" },
    marker: { colors: COLORS.palette, line: { color: "#0C1118", width: 2 } },
    hole: 0.35,
  }], { ...CL, margin: { t: 10, b: 10, l: 10, r: 10 }, showlegend: false }, CONF);

  renderRiskDetail(d);
}
