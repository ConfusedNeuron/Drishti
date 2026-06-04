# Drishti Frontend Code Guide

Claude reads this file before any frontend work. Updated: 2026-06-04.

## Directory Tree (canonical)

```
src/dashboard/
├── app.py                        ← StaticFiles + Jinja2 + /learn route + static_data router
├── templates/
│   ├── base.html                 ← shared header, CSS/JS links, blocks: nav/content/scripts/extra_head/title
│   ├── index.html                ← extends base; 5 dashboard tab panels + {% block scripts %}
│   └── learn.html                ← extends base; 7 static sections with KaTeX
├── static/
│   ├── css/
│   │   ├── theme.css             ← :root CSS variables ONLY
│   │   ├── layout.css            ← body, header, nav, grid, .page, @media + learn prose
│   │   ├── components.css        ← cards, tables, buttons, badges, callouts, memo, spinners, theme picker
│   │   └── tooltip.css           ← .tip-icon, .tip-popover styles
│   ├── js/
│   │   ├── theme.js              ← PRESETS, ACCENTS, applyTheme(), initTheme() called at bottom
│   │   ├── api.js                ← window.API = "" (only this line)
│   │   ├── charts.js             ← CL, CONF, COLORS, fmt(), pct()
│   │   ├── portfolio.js          ← riskData, _regimeLoaded, _icLoaded, showTab, importSample, importCSV, runRisk, renderOverview
│   │   ├── risk.js               ← renderRiskDetail, loadDrawdown, loadRegime
│   │   ├── research.js           ← loadIC
│   │   ├── spillover.js          ← loadDY, loadDCC
│   │   ├── copilot.js            ← loadMemo, askCopilot
│   │   └── tooltip.js            ← fetches glossary.json on DOMContentLoaded, attaches [data-tip] hover tips
│   └── data/
│       └── glossary.json         ← tooltip content keyed by string ID; 12 entries
└── routes/
    ├── portfolio.py, risk.py, research.py, copilot.py
    └── static_data.py            ← /api/static-data (lru_cached Bloomberg stats)
```

## JS Load Order (base.html — strict, do not reorder)

1. Plotly CDN — charts need it synchronously
2. `/static/js/theme.js` — CSS vars before any render; `initTheme()` runs immediately
3. `/static/js/api.js` — `window.API` available
4. `/static/js/charts.js` — `CL`/`CONF`/`COLORS`/`fmt`/`pct` available
5. `{% block scripts %}` — page-specific JS (index.html loads portfolio.js → copilot.js here)
6. `/static/js/tooltip.js` — attaches on DOMContentLoaded, must be last

## CSS Load Order (base.html — strict)

`theme.css` → `layout.css` → `components.css` → `tooltip.css`

## Global Scope Contracts

| Symbol | Declared in | Used by |
|--------|-------------|---------|
| `window.API` | api.js | all fetch() calls |
| `riskData`, `_regimeLoaded`, `_icLoaded` | portfolio.js | risk.js, research.js |
| `CL`, `CONF`, `COLORS`, `fmt`, `pct` | charts.js | portfolio.js, risk.js, spillover.js, research.js |
| `PRESETS`, `ACCENTS`, `_theme` | theme.js | rendered picker |
| `renderRiskDetail` | risk.js | called from portfolio.js:renderOverview |
| `loadIC` | research.js | called from portfolio.js:showTab |
| `loadDY`, `loadDCC` | spillover.js | called from portfolio.js:showTab |
| `loadRegime` | risk.js | called from portfolio.js:showTab |

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
