# Drishti Frontend Code Guide

Claude reads this file before any frontend work. Updated: 2026-07-06.

## Directory Tree (canonical)

```
src/dashboard/
├── app.py                        ← StaticFiles + Jinja2 + /learn route + static_data router
├── templates/
│   ├── base.html                 ← shared header (Learn link + home logo), CSS/JS links, blocks: nav/content/scripts/extra_head/title
│   ├── index.html                ← extends base; 8 dashboard tab panels (Portfolio/Overview, Risk, Research, Spillover, Events, Regimes, Frontier, Copilot) + {% block scripts %}
│   └── learn.html                ← extends base; 7 static sections with KaTeX
├── static/
│   ├── css/
│   │   ├── theme.css             ← :root CSS variables ONLY
│   │   ├── layout.css            ← body, header, nav, grid, .page, @media + learn prose
│   │   ├── components.css        ← cards, tables, buttons, badges, callouts, memo, spinners, theme picker,
│   │   │                            .header-link (Learn pill), .section-sub (panel subtitle), .chart-note (↳ reading note),
│   │   │                            #theme-btn (labeled "⬡ Theme" flex button), .pill-group/.pill-active (Frontier
│   │   │                            horizon/point buttons), .chip + .chip .x (Frontier candidate tags, removable)
│   │   └── tooltip.css           ← .tip-icon, .tip-popover styles
│   ├── js/
│   │   ├── theme.js              ← PRESETS, ACCENTS, applyTheme(), initTheme() called at bottom
│   │   ├── api.js                ← window.API = "" (only this line)
│   │   ├── charts.js             ← CL, CONF, COLORS, fmt(), pct()
│   │   ├── portfolio.js          ← riskData, _regimeLoaded, _icLoaded, _newsLoaded, _breachLoaded, _eventsLoaded,
│   │   │                            _regimesStudyLoaded, _diagLoaded, showTab, importSample, importCSV, runRisk, renderOverview,
│   │   │                            connectZerodha, submitZerodhaToken, loadPnl
│   │   ├── risk.js               ← renderRiskDetail, loadDrawdown, loadRegime
│   │   ├── research.js           ← loadIC, loadNews, loadBreach, loadDiagnostics (diagnostics ladder panel)
│   │   ├── spillover.js          ← loadDY, loadDCC, spillover-tab study/rolling charts
│   │   ├── events.js             ← Events tab (drawdown episodes, statistical levels)
│   │   ├── regimes.js            ← Regimes tab (bull/bear classification, HMM overlay)
│   │   ├── frontier.js           ← Frontier tab (horizon-matched efficient frontier, bootstrap band, tangency/CML, weight-gap diagnostic)
│   │   ├── copilot.js            ← loadMemo, askCopilot, mode badge (llm/deterministic_memo/safety_filter/llm_error)
│   │   └── tooltip.js            ← interactive hover-bridge tooltip (180ms hideTimer); popover stays open
│   │                                so "Read more →" link is clickable; fetches glossary.json on DOMContentLoaded
│   └── data/
│       └── glossary.json         ← tooltip content keyed by string ID; 12 entries
├── route_cache.py                ← in-process TTL cache wrapping regime + breach endpoints, keyed on (portfolio_id, as_of)
└── routes/
    ├── portfolio.py, risk.py, research.py, copilot.py
    └── static_data.py            ← /api/static-data (loads header badge: regime + connectedness from v2 artifacts)
```

## JS Load Order (base.html — strict, do not reorder)

1. Plotly CDN — charts need it synchronously
2. `/static/js/theme.js` — CSS vars before any render; `initTheme()` runs immediately
3. `/static/js/api.js` — `window.API` available
4. `/static/js/charts.js` — `CL`/`CONF`/`COLORS`/`fmt`/`pct` available
5. `{% block scripts %}` — page-specific JS, in this order: `portfolio.js` → `risk.js` → `research.js` → `spillover.js` → `events.js` → `regimes.js` → `frontier.js` → `copilot.js`
6. `/static/js/tooltip.js` — attaches on DOMContentLoaded, must be last

## CSS Load Order (base.html — strict)

`theme.css` → `layout.css` → `components.css` → `tooltip.css`

## Global Scope Contracts

| Symbol | Declared in | Used by |
|--------|-------------|---------|
| `window.API` | api.js | all fetch() calls |
| `riskData`, `_regimeLoaded`, `_icLoaded`, `_newsLoaded`, `_breachLoaded`, `_eventsLoaded`, `_regimesStudyLoaded`, `_diagLoaded`, `_frontierUniverseLoaded` | portfolio.js | risk.js, research.js, events.js, regimes.js, frontier.js |
| `CL`, `CONF`, `COLORS`, `fmt`, `pct` | charts.js | portfolio.js, risk.js, spillover.js, research.js, events.js, regimes.js, frontier.js |
| `PRESETS`, `ACCENTS`, `_theme` | theme.js | rendered picker |
| `renderRiskDetail` | risk.js | called from portfolio.js:renderOverview |
| `loadIC`, `loadNews`, `loadBreach`, `loadDiagnostics` | research.js | called from portfolio.js:showTab |
| `loadDY`, `loadDCC` | spillover.js | called from portfolio.js:showTab |
| `loadRegime` | risk.js | called from portfolio.js:showTab |
| `loadEvents` | events.js | called from portfolio.js:showTab (sets `_eventsLoaded`) |
| `loadRegimesStudy` | regimes.js | called from portfolio.js:showTab (sets `_regimesStudyLoaded`) |
| `connectZerodha`, `submitZerodhaToken`, `loadPnl` | portfolio.js | called from inline `onclick` in index.html (⚡ Connect Zerodha button, manual-token submit) and internally — `loadPnl()` also runs after `importSample()`/`importCSV()`; no new globals introduced |
| `frontierData`, `loadFrontierUniverse`, `runFrontier`, `selectFrontierHorizon`, `selectFrontierPoint`, `addFrontierCandidate`/`removeFrontierCandidate` | frontier.js | `loadFrontierUniverse` called from portfolio.js:showTab (sets `_frontierUniverseLoaded`, see note below); the rest called from inline `onclick` in index.html (horizon pills, Run button, point-selector buttons, candidate add/remove) |
| `renderFrontierChart`, `renderFrontierGap` | frontier.js | internal — called from `runFrontier()`'s success path only |

**Note:** unlike every other `_xLoaded` flag (set inside the async success path — see `portfolio.js` header comment), `_frontierUniverseLoaded` is set **synchronously** in `showTab()` before `loadFrontierUniverse()` even resolves. This is deliberate: a failed universe fetch shows an inline note in `#frontier-meta` instead of leaving the flag `false`, which would otherwise retry-fetch (and re-fail) every time the user re-clicks the Frontier tab.

**Note:** `tooltip.js` is an IIFE with no globals. It uses a module-scoped `hideTimer` to bridge the cursor gap between trigger and popover — do not add `pointer-events:none` to the `#tip-popover` div.

**Note:** the Holdings P&L panel (`#pnl-panel`) lives in the Overview tab, hidden until populated — `loadPnl()` fetches `GET /api/portfolio/pnl` and fills it after any import (sample, CSV, or Zerodha).

## How to Add a New Dashboard Tab

1. Add `<button onclick="showTab('mytab', this)">My Tab</button>` in `{% block nav %}` of `templates/index.html`
2. Add `<div id="tab-mytab" class="tab-panel">...</div>` in `{% block content %}`
3. Create `src/dashboard/static/js/mytab.js` with fetch/render logic
4. Add `<script src="/static/js/mytab.js"></script>` to `{% block scripts %}` in `index.html`

## How to Add a New Tooltip

1. Wrap the term: `<span data-tip="my-key">Term <i class="tip-icon">ⓘ</i></span>`
2. Add entry to `static/data/glossary.json`:
```json
"my-key": { "title": "...", "summary": "2-3 sentences.", "learn": "/learn#glossary" }
```
tooltip.js picks up all `[data-tip]` elements automatically on DOMContentLoaded.

## CSS Variable Reference

| Variable | Purpose | Default |
|----------|---------|---------|
| `--bg` | Page background | `#07090E` |
| `--surface` | Card/section background | `#0C1118` |
| `--surface-2` | Chart bg, inputs | `#111927` |
| `--ink` | Primary text | `#E6EDF3` |
| `--ink-2` | Secondary text | `#CDD9E5` |
| `--muted` | Labels, placeholders | `#7D8590` |
| `--line` | Borders | `#21262D` |
| `--line-2` | Stronger borders | `#2D3748` |
| `--primary` | Accent (gold default) | `#C9A227` |
| `--primary-light` | Hover accent | `#F0C842` |
| `--primary-dim` | Subtle accent bg | `rgba(201,162,39,0.12)` |
| `--ok` | Pass/positive | `#3FB950` |
| `--warn` | Warning | `#D29922` |
| `--danger` | Fail/negative | `#F85149` |
