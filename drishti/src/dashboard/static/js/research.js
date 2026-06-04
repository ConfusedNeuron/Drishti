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
