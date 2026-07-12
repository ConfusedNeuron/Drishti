// ── Market Sentiment (FinBERT) ─────────────────────────────────────────────

async function loadNews() {
  const panel = document.getElementById("news-panel");
  if (!panel) return;

  const statusEl = document.getElementById("news-status");
  if (statusEl) statusEl.textContent = "Loading…";

  try {
    const r = await fetch(window.API + "/api/research/news");
    const d = await r.json();
    if (!r.ok || d.status === "no_cache") {
      _renderNewsEmpty();
      return;
    }
    _renderNews(d);
    _newsLoaded = true;
  } catch (e) {
    if (statusEl) statusEl.textContent = "News unavailable.";
  }
}

async function refreshNews() {
  const btn = document.getElementById("news-refresh-btn");
  const statusEl = document.getElementById("news-status");
  if (btn) { btn.disabled = true; btn.textContent = "Refreshing…"; }
  if (statusEl) statusEl.textContent = "Fetching RSS + running FinBERT (may take 20–30 s)…";

  try {
    const r = await fetch(window.API + "/api/research/news/refresh", { method: "POST" });
    const d = await r.json();
    if (!r.ok) {
      if (statusEl) statusEl.textContent = d.detail || "Refresh failed.";
      return;
    }
    _renderNews(d);
  } catch (e) {
    if (statusEl) statusEl.textContent = "Refresh error: " + e;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Refresh"; }
  }
}

function _renderNewsEmpty() {
  const statusEl = document.getElementById("news-status");
  if (statusEl) statusEl.textContent = "No cached data. Click Refresh to fetch headlines.";
  const badges = document.getElementById("news-badges");
  if (badges) badges.innerHTML = "";
  const list = document.getElementById("news-list");
  if (list) list.innerHTML = "";
}

function _sentimentColor(label) {
  if (label === "positive") return "var(--ok)";
  if (label === "negative") return "var(--danger)";
  return "var(--muted)";
}

function _aggregateColor(agg) {
  if (agg === "Bullish") return "var(--ok)";
  if (agg === "Bearish") return "var(--danger)";
  return "var(--muted)";
}

function _renderNews(d) {
  const statusEl = document.getElementById("news-status");
  if (statusEl) {
    const ts = d.fetched_at ? new Date(d.fetched_at).toLocaleString() : "unknown";
    statusEl.textContent = `${d.n_sources} sources · ${d.headlines.length} headlines · fetched ${ts}`;
  }

  // Aggregate badges
  const badges = document.getElementById("news-badges");
  if (badges) {
    const aggColor = _aggregateColor(d.aggregate);
    badges.innerHTML = `
      <span style="color:${aggColor};font-weight:700;font-size:15px;margin-right:16px">${d.aggregate}</span>
      <span class="news-badge" style="color:var(--ok)">Bullish ${d.positive_pct.toFixed(0)}%</span>
      <span class="news-badge" style="color:var(--muted)">Neutral ${d.neutral_pct.toFixed(0)}%</span>
      <span class="news-badge" style="color:var(--danger)">Bearish ${d.negative_pct.toFixed(0)}%</span>`;
  }

  // Headline list — max 8 visible, scrollable
  const list = document.getElementById("news-list");
  if (!list) return;
  const top8 = (d.headlines || []).slice(0, 8);
  list.innerHTML = top8.map(h => {
    const chipColor = _sentimentColor(h.sentiment_label);
    const chip = `<span style="color:${chipColor};font-size:10px;font-weight:600;text-transform:uppercase;border:1px solid ${chipColor};border-radius:3px;padding:1px 5px">${h.sentiment_label}</span>`;
    const src = `<span style="color:var(--primary);font-size:10px;font-family:'JetBrains Mono',monospace;margin-right:8px">[${h.source}]</span>`;
    const link = h.link
      ? `<a href="${h.link}" target="_blank" rel="noopener" style="color:var(--ink);text-decoration:none">${h.title}</a>`
      : h.title;
    return `<div class="news-row">${src}${link}&nbsp;${chip}</div>`;
  }).join("");
}


// ── Breach Risk (XGBoost) ──────────────────────────────────────────────────

async function loadBreach() {
  const panel = document.getElementById("breach-panel");
  if (!panel) return;
  const statusEl = document.getElementById("breach-status");
  if (statusEl) statusEl.textContent = "Loading…";

  try {
    const r = await fetch(window.API + "/api/research/breach");
    const d = await r.json();
    if (!r.ok) {
      if (statusEl) statusEl.textContent = d.detail || "Breach data unavailable.";
      return;
    }
    _renderBreach(d);
    _breachLoaded = true;
  } catch (e) {
    if (statusEl) statusEl.textContent = "Breach endpoint error: " + e;
  }
}

function _breachColor(risk_level) {
  if (risk_level === "High")     return "var(--danger)";
  if (risk_level === "Elevated") return "var(--warn)";
  return "var(--ok)";
}

function _renderBreach(d) {
  const statusEl = document.getElementById("breach-status");

  if (!d.model_available) {
    if (statusEl) statusEl.textContent = d.note || "Model not available.";
    const probEl = document.getElementById("breach-prob");
    if (probEl) probEl.innerHTML = `<span style="color:var(--muted);font-size:13px">${d.note}</span>`;
    return;
  }

  if (statusEl) statusEl.textContent = "";

  const probEl = document.getElementById("breach-prob");
  const color = _breachColor(d.risk_level);
  if (probEl) {
    probEl.innerHTML = `
      <span style="font-size:42px;font-weight:700;color:${color};font-family:'JetBrains Mono',monospace">
        ${(d.breach_probability * 100).toFixed(1)}%
      </span>
      <span style="color:${color};font-size:13px;margin-left:10px;font-weight:600">${d.risk_level}</span>`;
  }

  // Feature importance bar chart
  const chartEl = document.getElementById("breach-chart");
  if (!chartEl || !d.top_features || !d.top_features.length) return;

  const feats = d.top_features.slice(0, 8);
  Plotly.newPlot(chartEl, [{
    type: "bar",
    orientation: "h",
    x: feats.map(f => f.importance),
    y: feats.map(f => f.feature),
    marker: { color: COLORS.gold },
    hovertemplate: "%{y}: %{x:.4f}<extra></extra>",
  }], {
    ...CL,
    margin: { t: 10, b: 30, l: 130, r: 20 },
    xaxis: {
      ...CL.xaxis,
      title: { text: "Importance (gain)", font: { size: 10 } },
    },
    yaxis: { ...CL.yaxis, autorange: "reversed" },
    height: 220,
  }, CONF);
}


// ── IC / Walk-forward (existing) ───────────────────────────────────────────

async function loadIC() {
  document.getElementById("ic-spinner").style.display = "block";
  try {
    const r = await fetch(window.API + "/api/research/ic");
    if (!r.ok) {
      document.getElementById("ic-table").textContent = "IC data unavailable — load portfolio + cached data first.";
      return;
    }
    const d = await r.json();
    const rows = d.ic_results.slice(0, 15);
    document.getElementById("ic-table").innerHTML = `
      <table>
        <tr><th>Factor</th><th>Target</th><th>Lag</th><th>IC Mean</th><th>ICIR</th><th>t-stat</th><th>p-value</th><th>BH Sig</th></tr>
        ${rows.map(row => `
          <tr>
            <td style="font-family:'JetBrains Mono',monospace">${row.factor}</td>
            <td style="font-family:'JetBrains Mono',monospace">${row.target}</td>
            <td style="font-family:'JetBrains Mono',monospace">${row.lag_days}d</td>
            <td style="font-family:'JetBrains Mono',monospace">${row.ic_mean.toFixed(3)}</td>
            <td style="font-family:'JetBrains Mono',monospace">${row.icir.toFixed(2)}</td>
            <td style="font-family:'JetBrains Mono',monospace" class="${Math.abs(row.t_stat) > 1.96 ? 'pass' : ''}">${row.t_stat.toFixed(2)}</td>
            <td style="font-family:'JetBrains Mono',monospace">${row.p_value.toFixed(3)}</td>
            <td>${row.bh_significant ? '<span class="pass">✓</span>' : '—'}</td>
          </tr>`).join("")}
      </table>
      <p style="font-size:11px;color:var(--muted);margin-top:8px;font-family:'JetBrains Mono',monospace">${d.note}</p>`;
    _icLoaded = true;
  } finally {
    document.getElementById("ic-spinner").style.display = "none";
  }
}

async function loadWalkForward() {
  const spinner = document.getElementById("wf-spinner");
  const container = document.getElementById("wf-container");
  if (!spinner || !container) return;
  spinner.style.display = "block";
  container.style.display = "none";
  try {
    const r = await fetch(window.API + "/api/research/walkforward");
    if (!r.ok) {
      container.innerHTML = `<p style="color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:12px">Walk-forward data unavailable — cached factor/sector data required.</p>`;
      container.style.display = "block";
      return;
    }
    const d = await r.json();

    if (!d.n_pairs || d.n_pairs === 0) {
      container.innerHTML = `<p style="color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:12px">No factor-sector pairs returned — check cached data.</p>`;
      container.style.display = "block";
      return;
    }

    // Build heatmap: rows = factors, cols = sectors
    const factors = d.factors;
    const sectors = d.sectors;
    // z[i] = row of Sharpe values for factors[i], across all sectors
    const z = factors.map(f =>
      sectors.map(s => {
        const v = d.sharpe_matrix[f] && d.sharpe_matrix[f][s];
        return (v !== null && v !== undefined) ? v : null;
      })
    );
    // text annotations: show value or "—"
    const text = z.map(row => row.map(v => v !== null ? v.toFixed(2) : "—"));

    Plotly.newPlot("wf-heatmap", [{
      type: "heatmap",
      x: sectors,
      y: factors,
      z: z,
      text: text,
      texttemplate: "%{text}",
      colorscale: [
        [0.0, COLORS.danger],
        [0.4, "#21262D"],
        [0.6, "#21262D"],
        [1.0, COLORS.ok],
      ],
      zmid: 0,
      colorbar: {
        title: { text: "OOS Sharpe", font: { size: 10, color: COLORS.muted } },
        tickfont: { size: 9, color: COLORS.muted },
        len: 0.8,
      },
      hovertemplate: "Factor: %{y}<br>Sector: %{x}<br>OOS Sharpe: %{z:.3f}<extra></extra>",
    }], {
      ...CL,
      margin: { t: 20, b: 80, l: 90, r: 20 },
      xaxis: { ...CL.xaxis, title: { text: "Sector", font: { size: 10 } } },
      yaxis: { ...CL.yaxis, title: { text: "Factor", font: { size: 10 } } },
      font: { ...CL.font, size: 11 },
    }, CONF);

    // Summary table beneath heatmap
    const sorted = [...d.metrics].sort((a, b) => b.oos_sharpe - a.oos_sharpe);
    const tableRows = sorted.map(m => {
      const sharpeClass = m.oos_sharpe > 0.5 ? "style='color:var(--ok)'" :
                          m.oos_sharpe < 0   ? "style='color:var(--danger)'" : "";
      return `<tr>
        <td style="font-family:'JetBrains Mono',monospace">${m.factor}</td>
        <td style="font-family:'JetBrains Mono',monospace">${m.target}</td>
        <td style="font-family:'JetBrains Mono',monospace">${m.lag_days}d</td>
        <td style="font-family:'JetBrains Mono',monospace" ${sharpeClass}>${m.oos_sharpe.toFixed(2)}</td>
        <td style="font-family:'JetBrains Mono',monospace">${(m.oos_total_return * 100).toFixed(1)}%</td>
        <td style="font-family:'JetBrains Mono',monospace">${(m.oos_max_dd * 100).toFixed(1)}%</td>
        <td style="font-family:'JetBrains Mono',monospace">${(m.oos_win_rate * 100).toFixed(1)}%</td>
        <td style="font-family:'JetBrains Mono',monospace">${m.oos_obs}</td>
      </tr>`;
    }).join("");

    document.getElementById("wf-table").innerHTML = `
      <table>
        <tr><th>Factor</th><th>Sector</th><th>Lag</th><th>OOS Sharpe</th><th>OOS Return</th><th>Max DD</th><th>Win Rate</th><th>OOS Obs</th></tr>
        ${tableRows}
      </table>
      <p style="font-size:11px;color:var(--muted);margin-top:8px;font-family:'JetBrains Mono',monospace">${d.note}</p>`;

    container.style.display = "block";
  } finally {
    spinner.style.display = "none";
  }
}

// ── Model Diagnostics Ladder ───────────────────────────────────────────────

const _DIAG_LABELS = {
  adf: "Stationarity (ADF)",
  returns_lb: "Autocorrelation (Ljung-Box)",
  arch_lm: "ARCH effects (ARCH-LM)",
};

// Backend emits nan for failed fits; clean_json turns nan → JSON null.
// Every numeric cell goes through this so one failed model can't blank the panel.
const _diagNum = (v, d) =>
  (typeof v !== "number" || Number.isNaN(v)) ? "—" : v.toFixed(d);

function _diagModelLabel(key) {
  // "garch_12" → "GARCH(1,2)", "gjr_11" → "GJR(1,1)"
  const [family, order] = key.split("_");
  if (!order) return family.toUpperCase();
  return `${family.toUpperCase()}(${order.split("").join(",")})`;
}

function _diagTestRow(label, t) {
  return `
    <tr>
      <td>${label}</td>
      <td style="font-family:'JetBrains Mono',monospace">${_diagNum(t.statistic, 4)}</td>
      <td style="font-family:'JetBrains Mono',monospace">${_diagNum(t.p_value, 4)}</td>
      <td>${t.conclusion || "—"}</td>
    </tr>`;
}

function _diagOrderScanTable(orderScan) {
  const rows = Object.entries(orderScan).map(([model, m]) => {
    const note = m.error
      ? `<span style="color:var(--muted)">fit failed: ${m.error}</span>`
      : (m.gamma != null
          ? `${_diagNum(m.gamma, 4)} (p=${_diagNum(m.gamma_p, 4)})`
          : "—");
    return `
      <tr>
        <td style="font-family:'JetBrains Mono',monospace">${_diagModelLabel(model)}</td>
        <td style="font-family:'JetBrains Mono',monospace">${_diagNum(m.bic, 2)}</td>
        <td style="font-family:'JetBrains Mono',monospace">${_diagNum(m.aic, 2)}</td>
        <td style="font-family:'JetBrains Mono',monospace">${note}</td>
      </tr>`;
  }).join("");
  return `
    <table>
      <tr><th>Model</th><th>BIC</th><th>AIC</th><th>Asymmetry γ (GJR only) / note</th></tr>
      ${rows}
    </table>`;
}

async function loadDiagnostics() {
  const spin = document.getElementById("diag-spinner");
  spin.style.display = "block";
  try {
    const r = await fetch(window.API + "/api/research/diagnostics");
    if (!r.ok) {
      document.getElementById("diag-tables").textContent = "Diagnostics unavailable — cached data required.";
      return;
    }
    const d = await r.json();
    const u = d.univariate;

    const ladderRows = Object.keys(_DIAG_LABELS)
      .filter(k => u[k])
      .map(k => _diagTestRow(_DIAG_LABELS[k], u[k]))
      .join("");

    const ladderTable = `
      <h3 style="margin-top:12px">Univariate ladder (portfolio returns)</h3>
      <table>
        <tr><th>Test</th><th>Statistic</th><th>p-value</th><th>Conclusion</th></tr>
        ${ladderRows}
      </table>`;

    const orderScanBlock = u.order_scan ? `
      <h3 style="margin-top:12px">GARCH order scan (best BIC wins)</h3>
      ${_diagOrderScanTable(u.order_scan)}` : "";

    const residRows = ("std_resid_lb_p" in u || "std_resid_sq_lb_p" in u) ? `
      <h3 style="margin-top:12px">Standardized residual checks (fitted GARCH)</h3>
      <table>
        <tr><th>Check</th><th>p-value</th></tr>
        <tr>
          <td>Std. residuals — Ljung-Box(10)</td>
          <td style="font-family:'JetBrains Mono',monospace">${_diagNum(u.std_resid_lb_p, 4)}</td>
        </tr>
        <tr>
          <td>Std. residuals² — Ljung-Box(10) (remaining ARCH)</td>
          <td style="font-family:'JetBrains Mono',monospace">${_diagNum(u.std_resid_sq_lb_p, 4)}</td>
        </tr>
      </table>` : "";

    const m = d.multivariate;
    const multiTable = m ? `
      <h3 style="margin-top:12px">Multivariate — constant-correlation test (sector panel)</h3>
      <table>
        <tr><th>Test</th><th>Statistic</th><th>p-value</th><th>Conclusion</th></tr>
        ${_diagTestRow(m.name || "Engle-Sheppard CCC", m)}
      </table>` : "";

    document.getElementById("diag-tables").innerHTML =
      ladderTable + orderScanBlock + residRows + multiTable;
    _diagLoaded = true;
  } catch (e) {
    document.getElementById("diag-tables").textContent = "Diagnostics error: " + e;
  } finally {
    spin.style.display = "none";
  }
}
