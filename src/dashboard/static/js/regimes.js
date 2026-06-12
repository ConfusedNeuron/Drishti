async function loadRegimesStudy() {
  const el = document.getElementById("regimes-placeholder");
  if (el) el.textContent = "Loading regime study…";

  try {
    const r = await fetch(window.API + "/api/research/regimes-study");
    if (!r.ok) {
      if (el) el.innerHTML = r.status === 503
        ? "<p class='muted'>Regime study artifact not built yet. Run <code>scripts/build_regime_study.py</code> with v2 data.</p>"
        : "<p class='muted'>Regime data unavailable (status " + r.status + ").</p>";
      return;
    }
    const data = await r.json();
    if (el) el.remove();
    _regimesStudyLoaded = true;
    renderRegimesStudy(data);
  } catch (e) {
    if (el) el.innerHTML = "<p class='muted'>Regime study load error: " + e.message + "</p>";
  }
}

function renderRegimesStudy(data) {
  // Chart 1: Bull/Bear timeline — distance from peak over time
  const series = data.regime_series || [];
  if (series.length) {
    const dates = series.map(r => r.date);
    const pcts = series.map(r => (r.pct_from_peak || 0) * 100);
    Plotly.newPlot("regimes-timeline-chart", [{
      type: "scatter",
      mode: "lines",
      x: dates,
      y: pcts,
      line: { color: "var(--primary)", width: 1.5 },
      hovertemplate: "<b>%{x}</b><br>%{y:.1f}% from peak<extra></extra>",
    }], {
      ...CL,
      title: { text: "NIFTY 100: Distance from Peak (Bull/Bear Regime)", font: { color: "var(--ink)", size: 14 } },
      xaxis: { color: "var(--ink-2)" },
      yaxis: { title: "% from peak", color: "var(--ink-2)" },
      shapes: (data.bull_bear_episodes || []).map(e => ({
        type: "rect", xref: "x", yref: "paper",
        x0: e.start, x1: e.end || dates[dates.length - 1],
        y0: 0, y1: 1,
        fillcolor: e.type === "bear" ? "rgba(248,81,73,0.08)" : "rgba(63,185,80,0.05)",
        line: { width: 0 },
      })),
    }, CONF);
  }

  // Stats table — regime_signs: {bull:{n_days, mean_daily_ret, ann_vol, ...}, bear:{...}}
  const stats = data.regime_signs || {};
  const statsEl = document.getElementById("regimes-stats");
  if (statsEl && Object.keys(stats).length) {
    const rows = Object.entries(stats).map(([regime, s]) => `
      <tr>
        <td>${regime}</td>
        <td>${s.n_days !== undefined ? s.n_days : "—"}</td>
        <td>${s.mean_daily_ret !== undefined ? (s.mean_daily_ret * 100).toFixed(2) + "%" : "—"}</td>
        <td>${s.ann_vol !== undefined ? (s.ann_vol * 100).toFixed(1) + "%" : "—"}</td>
        <td>${s.worst_day !== undefined ? (s.worst_day * 100).toFixed(1) + "%" : "—"}</td>
        <td>${s.skew !== undefined ? s.skew.toFixed(2) : "—"}</td>
        <td>${s.pct_up_days !== undefined ? (s.pct_up_days * 100).toFixed(0) + "%" : "—"}</td>
      </tr>`).join("");
    statsEl.innerHTML = `
      <table class="data-table">
        <thead><tr><th>Regime</th><th>Days</th><th>Daily Ret</th><th>Ann Vol</th><th>Worst Day</th><th>Skew</th><th>% Up Days</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  // Chart 2: HMM high-vol probability — hmm_prob: [{date, p_high_vol}]
  const hmm = data.hmm_prob || [];
  if (hmm.length) {
    Plotly.newPlot("regimes-hmm-chart", [{
      type: "scatter", mode: "lines",
      x: hmm.map(h => h.date),
      y: hmm.map(h => h.p_high_vol * 100),
      fill: "tozeroy",
      fillcolor: "rgba(248,81,73,0.15)",
      line: { color: "var(--danger)", width: 1.5 },
      hovertemplate: "<b>%{x}</b><br>P(high-vol): %{y:.1f}%<extra></extra>",
    }], {
      ...CL,
      title: { text: "HMM High-Volatility State Probability", font: { color: "var(--ink)", size: 14 } },
      xaxis: { color: "var(--ink-2)" },
      yaxis: { title: "P(high-vol) %", range: [0, 100], color: "var(--ink-2)" },
    }, CONF);
  }

  // Current state KPI
  const cs = data.current_state || {};
  const csEl = document.getElementById("regimes-current-state");
  if (csEl && Object.keys(cs).length) {
    const regime = cs.bull_bear_regime || "unknown";
    const color = regime === "bear" ? "var(--danger)" : "var(--ok)";
    csEl.innerHTML = `
      <div class="kpi-row">
        <div class="kpi-card"><span class="kpi-label">Regime</span><span class="kpi-value" style="color:${color}">${regime.toUpperCase()}</span></div>
        <div class="kpi-card"><span class="kpi-label">Drawdown from Peak</span><span class="kpi-value">${cs.drawdown_from_peak !== undefined ? (cs.drawdown_from_peak * 100).toFixed(1) + "%" : "—"}</span></div>
        <div class="kpi-card"><span class="kpi-label">% to Bear Threshold</span><span class="kpi-value">${cs.pct_to_bear_threshold !== undefined ? (cs.pct_to_bear_threshold * 100).toFixed(1) + "%" : "—"}</span></div>
      </div>
    `;
  }
}
