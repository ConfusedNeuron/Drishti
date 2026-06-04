function renderRiskDetail(d) {
  const bt = d.backtest;
  if (!bt.error) {
    document.getElementById("backtest-table").innerHTML = `
      <table>
        <tr><th>Metric</th><th>Value</th><th>Result</th></tr>
        <tr><td>Confidence</td><td>${(bt.confidence * 100).toFixed(0)}%</td><td></td></tr>
        <tr><td>Observations</td><td>${bt.obs}</td><td></td></tr>
        <tr><td>Violations</td><td>${bt.violations} observed vs ${bt.kupiec.expected_violations.toFixed(1)} expected</td><td></td></tr>
        <tr><td>Kupiec LR (p-value)</td><td>${bt.kupiec.lr_statistic.toFixed(3)} (p=${bt.kupiec.p_value.toFixed(3)})</td>
            <td class="${bt.kupiec.pass_ ? 'pass' : 'fail'}">${bt.kupiec.pass_ ? "✓ Pass" : "✗ Fail"}</td></tr>
        <tr><td>Christoffersen (p-value)</td><td>${bt.christoffersen.lr_statistic.toFixed(3)} (p=${bt.christoffersen.p_value.toFixed(3)})</td>
            <td class="${bt.christoffersen.pass_ ? 'pass' : 'fail'}">${bt.christoffersen.pass_ ? "✓ Pass" : "✗ Fail"}</td></tr>
        <tr><td colspan="2" style="font-style:italic;color:var(--muted)">${bt.verdict}</td><td></td></tr>
      </table>`;
  }
  const stress = d.stress_scenarios || [];
  document.getElementById("stress-table").innerHTML = `
    <table>
      <tr><th>Scenario</th><th>Loss (₹)</th><th>Loss (%)</th></tr>
      ${stress.map(s => `
        <tr>
          <td>${s.description}</td>
          <td style="color:var(--danger);font-family:'JetBrains Mono',monospace">₹${fmt(Math.abs(s.portfolio_loss))}</td>
          <td style="color:var(--danger);font-family:'JetBrains Mono',monospace">${pct(s.loss_percent)}</td>
        </tr>`).join("")}
    </table>`;
}

async function loadDrawdown() {
  const r = await fetch(window.API + "/api/risk/drawdown-series");
  if (!r.ok) return;
  const d = await r.json();
  Plotly.newPlot("dd-chart", [{
    type: "scatter", mode: "lines",
    x: d.dates, y: d.values.map(v => v * 100),
    fill: "tozeroy", fillcolor: "rgba(248,81,73,0.12)",
    line: { color: COLORS.danger, width: 1.5 },
    name: "Drawdown (%)"
  }], {
    ...CL,
    margin: { t: 10, b: 40, l: 55, r: 16 },
    yaxis: { ...CL.yaxis, title: { text: "Drawdown (%)", font: { size: 10 } }, ticksuffix: "%" },
    xaxis: { ...CL.xaxis, type: "date" },
  }, CONF);
}

async function loadRegime() {
  if (_regimeLoaded) return;
  document.getElementById("regime-spinner").style.display = "block";
  try {
    const r = await fetch(window.API + "/api/research/regime");
    if (!r.ok) { document.getElementById("regime-info").textContent = "Regime unavailable."; return; }
    const d = await r.json();
    const label = d.current_label || "unknown";
    document.getElementById("regime-badge").innerHTML =
      `<span class="badge badge-${label}">${label.replace("_", "-")}</span>`;
    document.getElementById("regime-info").innerHTML =
      `<p>Current: <strong>${label.toUpperCase()}</strong> — ${d.consecutive_days} consecutive days</p>` +
      (d.low_vol && d.high_vol ? `
        <table style="width:auto;margin-top:12px">
          <tr><th>Regime</th><th>Regime-Conditioned VaR</th><th>Obs</th></tr>
          <tr><td>Low-Vol</td><td style="font-family:'JetBrains Mono',monospace">₹${fmt(d.low_vol.var_amount)} (${pct(d.low_vol.var_percent)})</td><td>${d.low_vol.obs}</td></tr>
          <tr><td>High-Vol</td><td style="font-family:'JetBrains Mono',monospace;color:var(--danger)">₹${fmt(d.high_vol.var_amount)} (${pct(d.high_vol.var_percent)})</td><td>${d.high_vol.obs}</td></tr>
        </table>` : "");
    if (d.regime_history) {
      const rh = d.regime_history;
      Plotly.newPlot("regime-chart", [{
        type: "scatter", mode: "lines", fill: "tozeroy",
        x: rh.dates, y: rh.prob_high_vol.map(p => p * 100),
        fillcolor: "rgba(248,81,73,0.12)", line: { color: COLORS.danger, width: 1.5 },
        name: "P(High-Vol Regime) %"
      }], {
        ...CL,
        margin: { t: 10, b: 40, l: 60, r: 16 },
        yaxis: { ...CL.yaxis, title: { text: "P(High-Vol) %", font: { size: 10 } }, range: [0, 100], ticksuffix: "%" },
        xaxis: { ...CL.xaxis, type: "date" },
        shapes: [{ type: "line", x0: rh.dates[0], x1: rh.dates.slice(-1)[0],
                   y0: 50, y1: 50, line: { dash: "dot", color: "#2D3748", width: 1 } }],
      }, CONF);
    }
    _regimeLoaded = true;
  } finally {
    document.getElementById("regime-spinner").style.display = "none";
  }
}
