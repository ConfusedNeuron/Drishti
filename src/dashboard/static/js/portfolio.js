let riskData = null;
let _regimeLoaded = false;
let _icLoaded = false;
let _newsLoaded = false;
let _breachLoaded = false;
let _eventsLoaded = false;
let _regimesStudyLoaded = false;
let _diagLoaded = false;
let _frontierUniverseLoaded = false;
let _spilloverLabLoaded = false;

function showTab(name, btn) {
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll("nav button").forEach(b => b.classList.remove("active"));
  document.getElementById("tab-" + name).classList.add("active");
  btn.classList.add("active");

  if (name === "research") {
    if (!_newsLoaded)   loadNews();
    if (!_breachLoaded) loadBreach();
    if (!_icLoaded)     loadIC();
    if (!_diagLoaded)   loadDiagnostics();
  }
  if (name === "spillover") {
    loadDY(); loadDCC(); loadRollingSpillover();
    // Set synchronously (mirrors the frontier universe flag) — a failed catalog
    // fetch shows an inline note in #lab-error and must not retry-loop every
    // time the user re-clicks the Spillover tab.
    if (!_spilloverLabLoaded) { _spilloverLabLoaded = true; loadSpilloverCatalog(); }
  }
  if (name === "events") {
    if (!_eventsLoaded) loadEvents();
  }
  if (name === "regimes") {
    if (!_regimesStudyLoaded) loadRegimesStudy();
  }
  if (name === "risk") {
    if (riskData) renderRiskDetail(riskData);
    if (!_regimeLoaded) loadRegime();
  }
  if (name === "frontier") {
    // Set synchronously (not in the async success path like other _xLoaded flags) —
    // a failed universe fetch shows an inline note in #frontier-meta and must not
    // retry-loop every time the user re-clicks the Frontier tab.
    if (!_frontierUniverseLoaded) { _frontierUniverseLoaded = true; loadFrontierUniverse(); }
  }
}

async function importSample() {
  const r = await fetch(window.API + "/api/portfolio/import/sample?sample_id=nifty-demo-2026", { method: "POST" });
  if (!r.ok) { alert("Sample import failed: " + (await r.text())); return; }
  document.getElementById("kpi-source").textContent = "Sample portfolio loaded";
  document.getElementById("run-btn").disabled = false;
  loadPnl();
}

async function importCSV(input) {
  const fd = new FormData();
  fd.append("file", input.files[0]);
  const r = await fetch(window.API + "/api/portfolio/import/csv", { method: "POST", body: fd });
  if (!r.ok) { alert("CSV import failed: " + (await r.text())); return; }
  document.getElementById("kpi-source").textContent = "CSV portfolio loaded";
  document.getElementById("run-btn").disabled = false;
  loadPnl();
}

async function connectZerodha() {
  const r = await fetch(window.API + "/api/portfolio/zerodha/login");
  if (!r.ok) {
    let msg = "Zerodha login unavailable.";
    try { msg = (await r.json()).detail || msg; } catch (e) {}
    alert(msg);
    return;
  }
  const d = await r.json();
  window.open(d.login_url, "_blank");
  const row = document.getElementById("zerodha-manual");
  document.getElementById("zerodha-manual-hint").textContent =
    "If the Kite app's redirect URL points back here you'll return automatically. " +
    "Otherwise copy the request_token from the redirected URL and paste it below.";
  row.style.display = "block";
}

async function submitZerodhaToken() {
  const tok = document.getElementById("zerodha-token-input").value.trim();
  if (!tok) { alert("Paste the request_token first."); return; }
  const r = await fetch(window.API + "/api/portfolio/zerodha/token", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_token: tok }),
  });
  if (!r.ok) {
    let msg = "Token exchange failed.";
    try { msg = (await r.json()).detail || msg; } catch (e) {}
    alert(msg);
    return;
  }
  const snap = await r.json();
  const n = (snap.holdings || []).length;
  document.getElementById("kpi-source").textContent = "Zerodha (" + n + " holdings)";
  document.getElementById("run-btn").disabled = false;
  document.getElementById("zerodha-manual").style.display = "none";
  loadPnl();
}

async function loadPnl() {
  const r = await fetch(window.API + "/api/portfolio/pnl");
  if (!r.ok) return;
  const d = await r.json();
  const tbody = document.getElementById("pnl-tbody");
  const tfoot = document.getElementById("pnl-tfoot");
  tbody.innerHTML = (d.rows || []).map(row => {
    const cls = row.pnl >= 0 ? "ok" : "danger";
    const pnlPct = row.pnl_pct == null ? "—" : pct(row.pnl_pct);
    return `<tr>
      <td>${row.symbol}</td><td>${row.sector || "—"}</td>
      <td style="text-align:right">${fmt(row.quantity)}</td>
      <td style="text-align:right">₹${fmt(row.average_price, 2)}</td>
      <td style="text-align:right">₹${fmt(row.last_price, 2)}</td>
      <td style="text-align:right">₹${fmt(row.invested)}</td>
      <td style="text-align:right">₹${fmt(row.market_value)}</td>
      <td style="text-align:right;color:var(--${cls})">₹${fmt(row.pnl)}</td>
      <td style="text-align:right;color:var(--${cls})">${pnlPct}</td>
      <td style="text-align:right">${pct(row.weight)}</td>
    </tr>`;
  }).join("");
  const t = d.totals || {};
  const tcls = (t.pnl || 0) >= 0 ? "ok" : "danger";
  const tPct = t.pnl_pct == null ? "—" : pct(t.pnl_pct);
  tfoot.innerHTML = `<tr style="font-weight:600;border-top:1px solid var(--line-2)">
    <td>Total</td><td></td><td></td><td></td><td></td>
    <td style="text-align:right">₹${fmt(t.invested)}</td>
    <td style="text-align:right">₹${fmt(t.market_value)}</td>
    <td style="text-align:right;color:var(--${tcls})">₹${fmt(t.pnl)}</td>
    <td style="text-align:right;color:var(--${tcls})">${tPct}</td>
    <td></td></tr>`;
  document.getElementById("pnl-panel").style.display = "block";
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

// Header badge on page load from precomputed artifacts (until live risk data replaces it)
async function initHeaderBadge() {
  try {
    const r = await fetch(window.API + "/api/static-data");
    if (!r.ok) return;
    const d = await r.json();
    const el = document.getElementById("regime-badge");
    if (!d.regime || !el || el.innerHTML) return;
    el.innerHTML = `<span class="badge badge-${d.regime}" title="Precomputed market state (NIFTY), data as of ${d.data_as_of || "n/a"}">${d.regime}</span>`;
  } catch (e) { /* badge is decorative — stay silent */ }
}
document.addEventListener("DOMContentLoaded", initHeaderBadge);

document.addEventListener("DOMContentLoaded", () => {
  const params = new URLSearchParams(location.search);
  const z = params.get("zerodha");
  if (z === "connected") {
    fetch(window.API + "/api/portfolio/current").then(r => r.ok ? r.json() : null).then(snap => {
      if (!snap) return;
      const n = (snap.holdings || []).length;
      document.getElementById("kpi-source").textContent = "Zerodha (" + n + " holdings)";
      document.getElementById("run-btn").disabled = false;
      loadPnl();
    });
    history.replaceState({}, "", location.pathname);
  } else if (z === "error") {
    alert("Zerodha connection failed: " + (params.get("reason") || "unknown error"));
    history.replaceState({}, "", location.pathname);
  }
});
