async function loadEvents() {
  const el = document.getElementById("events-placeholder");
  if (el) el.textContent = "Loading events data…";

  try {
    const r = await fetch(window.API + "/api/research/events");
    if (!r.ok) {
      if (el) el.innerHTML = r.status === 503
        ? "<p class='muted'>Events artifact not built yet. Run <code>scripts/build_events_study.py</code> with v2 data.</p>"
        : "<p class='muted'>Events data unavailable (status " + r.status + ").</p>";
      return;
    }
    const data = await r.json();
    if (el) el.remove();
    _eventsLoaded = true;
    renderEvents(data);
  } catch (e) {
    if (el) el.innerHTML = "<p class='muted'>Events load error: " + e.message + "</p>";
  }
}

function renderEvents(data) {
  const episodes = data.episodes || [];
  if (!episodes.length) {
    const chartEl = document.getElementById("events-timeline-chart");
    if (chartEl) chartEl.innerHTML = "<p class='muted'>No episodes detected.</p>";
    return;
  }

  // Chart 1: Episode depth horizontal bar chart
  const labels = episodes.map(e => e.label || "Episode");
  const depths = episodes.map(e => Math.abs(e.depth || 0) * 100);
  const causes = episodes.map(e => e.cause || "");

  Plotly.newPlot("events-timeline-chart", [{
    type: "bar",
    orientation: "h",
    y: labels,
    x: depths,
    text: depths.map(d => d.toFixed(1) + "%"),
    textposition: "outside",
    hovertext: causes,
    hovertemplate: "<b>%{y}</b><br>Depth: %{x:.1f}%<br>%{hovertext}<extra></extra>",
    marker: { color: "var(--danger)" },
  }], {
    ...CL,
    title: { text: "Episode Depths (peak-to-trough)", font: { color: "var(--ink)", size: 14 } },
    xaxis: { title: "Fall (%)", color: "var(--ink-2)" },
    yaxis: { automargin: true, color: "var(--ink-2)" },
    margin: { l: 200, r: 60, t: 40, b: 50 },
  }, CONF);

  // Chart 2: Recovery days bar chart
  const recoveryDays = episodes.map(e => e.recovery_days || null);
  const validRecovery = recoveryDays.map(d => d === null ? 0 : d);
  const recColors = recoveryDays.map(d => d === null ? "var(--warn)" : "var(--ok)");

  Plotly.newPlot("events-recovery-chart", [{
    type: "bar",
    x: labels,
    y: validRecovery,
    text: recoveryDays.map(d => d === null ? "Ongoing" : d + "d"),
    textposition: "outside",
    marker: { color: recColors },
    hovertemplate: "<b>%{x}</b><br>Recovery: %{text}<extra></extra>",
  }], {
    ...CL,
    title: { text: "Recovery Duration (trough to prior peak)", font: { color: "var(--ink)", size: 14 } },
    xaxis: { tickangle: -30, color: "var(--ink-2)" },
    yaxis: { title: "Days", color: "var(--ink-2)" },
    margin: { l: 60, r: 30, t: 40, b: 120 },
  }, CONF);

  // Statistical levels card
  const sl = data.statistical_levels || {};
  const slEl = document.getElementById("events-stat-levels");
  if (slEl && sl.median_fall !== undefined) {
    slEl.innerHTML = `
      <div class="kpi-row">
        <div class="kpi-card"><span class="kpi-label">Median Fall</span><span class="kpi-value">${(sl.median_fall * 100).toFixed(1)}%</span></div>
        <div class="kpi-card"><span class="kpi-label">75th Pctl</span><span class="kpi-value">${(sl.p75_fall * 100).toFixed(1)}%</span></div>
        <div class="kpi-card"><span class="kpi-label">90th Pctl</span><span class="kpi-value">${(sl.p90_fall * 100).toFixed(1)}%</span></div>
        <div class="kpi-card"><span class="kpi-label">Max Fall</span><span class="kpi-value">${(sl.max_fall * 100).toFixed(1)}%</span></div>
      </div>
      <p class="chart-note">↳ ${sl.note || ""}</p>
    `;
  }

  // Practitioner appendix (if present)
  const paEl = document.getElementById("events-practitioner");
  if (paEl && data.practitioner_appendix) {
    paEl.style.display = "block";
    paEl.innerHTML = `<p class="muted">${data.practitioner_appendix.disclaimer || ""}</p>`;
  }
}
