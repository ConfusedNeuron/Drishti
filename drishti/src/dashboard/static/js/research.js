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
