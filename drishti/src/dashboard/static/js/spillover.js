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
