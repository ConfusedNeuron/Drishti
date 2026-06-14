# Drishti — Frontend & Data Layer Overhaul
**Date:** 2026-06-03  
**Status:** Approved for implementation  
**Tracks:** A (Frontend) · B (Data Layer)

---

## 1. Context

Drishti is a local-first quant risk research platform for Indian equity portfolios (IIM Calcutta PGDBA FRM course project). The current frontend is a single 1059-line `index.html` file. The data pipeline is entirely Bloomberg-dependent (FRTL lab, manual pull). This overhaul splits the frontend into a maintainable multi-file Jinja2 architecture and adds a free public data layer to keep the cache fresh after the Bloomberg pull ends.

---

## 2. Track A — Frontend Overhaul

### 2.1 Architecture: Jinja2 Templates (Option B)

Switch from serving raw HTML via `HTMLResponse` to FastAPI `Jinja2Templates`. This enables a shared `base.html` (header, nav, CSS/JS imports) extended by all pages — zero HTML duplication.

**`app.py` changes required:**
1. Add `app.mount("/static", StaticFiles(directory=_STATIC), name="static")` — currently missing, will cause 404 for all split CSS/JS files.
2. Add `Jinja2Templates(directory=_TEMPLATES)` instance.
3. Replace the `root()` HTMLResponse with a `TemplateResponse("index.html", {"request": request, ...})`.
4. Add `@app.get("/learn")` route returning `TemplateResponse("learn.html", ...)`.

**Directory layout after overhaul:**

```
src/dashboard/
├── app.py                        ← updated (StaticFiles + Jinja2 + /learn route)
├── templates/                    ← NEW: Jinja2 renders these server-side
│   ├── base.html                 ← shared header, nav, CSS/JS <link>/<script> tags
│   ├── index.html                ← extends base; all 5 dashboard tabs
│   └── learn.html                ← extends base; Know/Learn page
├── static/                       ← served at /static by StaticFiles
│   ├── css/
│   │   ├── theme.css             ← CSS variables + 6-preset theme definitions
│   │   ├── layout.css            ← header, nav, page, grid
│   │   ├── components.css        ← cards, tables, buttons, badges, callouts, spinners
│   │   └── tooltip.css           ← ⓘ icon + floating tooltip card styles
│   └── js/
│       ├── theme.js              ← applyTheme(), renderThemePicker(), localStorage
│       ├── api.js                ← all fetch() wrappers; declares window.API = ""
│       ├── charts.js             ← shared Plotly config (CL, CONF, COLORS) + chart builders
│       ├── portfolio.js          ← importSample(), importCSV(), runRisk(), KPI updates
│       ├── risk.js               ← Risk Detail tab: backtest table, stress table, regime chart
│       ├── research.js           ← Factor Research tab: IC table, regime info
│       ├── spillover.js          ← Spillover tab: DY chart, DCC chart
│       ├── copilot.js            ← Memo generation + chat (askCopilot)
│       └── tooltip.js            ← ⓘ icon injection; hover/focus popover logic
│   └── data/
│       └── glossary.json         ← tooltip content keyed by string ID; served at /static/data/glossary.json
├── routes/
│   ├── (existing: portfolio, risk, research, copilot)
│   └── static_data.py            ← NEW: /api/static-data endpoint

docs/frontend/
└── code.md                       ← structure guide (Claude reads this for all frontend work)
```

**JS load order in `base.html`** (strict, must not be reordered):
```html
<script src="/static/js/theme.js"></script>     <!-- 1: CSS vars before any render -->
<script src="/static/js/api.js"></script>        <!-- 2: window.API available -->
<script src="/static/js/charts.js"></script>     <!-- 3: Plotly helpers ready -->
<script src="/static/js/portfolio.js"></script>
<script src="/static/js/risk.js"></script>
<script src="/static/js/research.js"></script>
<script src="/static/js/spillover.js"></script>
<script src="/static/js/copilot.js"></script>
<script src="/static/js/tooltip.js"></script>   <!-- last: all DOM ready -->
```

**CSS load order in `base.html`** (strict):
```html
<link rel="stylesheet" href="/static/css/theme.css">      <!-- 1: variables -->
<link rel="stylesheet" href="/static/css/layout.css">
<link rel="stylesheet" href="/static/css/components.css">
<link rel="stylesheet" href="/static/css/tooltip.css">
```

---

### 2.2 Static vs Dynamic Content Strategy

The dashboard has two modes depending on whether data is loaded:

**No data (presentation mode):**
- All 5 tabs render with static content: dense finance/stats prose, formulas (KaTeX), key concepts, methodology explanations, and pre-written findings from the NIFTY 200 Bloomberg analysis.
- A small set of "live numbers" are injected at page load from `/api/static-data` — these show the pre-computed results from our Bloomberg cache (current regime, total DY connectedness, IC signal count, sample portfolio VaR range). If the cache is absent, these slots show `"—"` gracefully.
- The page reads completely as a standalone course document.

**Data loaded (interactive mode):**
- The same sections gain live context: "Your portfolio VaR is X% — [high / typical / low] for a 12-stock NIFTY 200 portfolio."
- Contextual benchmarks come from the static findings (e.g., "typical NIFTY 200 constituent 99% 10-day VaR range: 4–9%").
- No visual mode switch — the page simply becomes richer as data is available.

**`/api/static-data` endpoint** (`routes/static_data.py`):
- Runs once at server startup; results cached in memory.
- Reads from Bloomberg parquet cache: last HMM regime + probability, total DY connectedness, BH-significant IC signal count, sample portfolio VaR range.
- Returns `{"regime": "low-vol", "regime_prob": 0.87, "dy_total": 62.3, "ic_signals": 14, "var_range": [4.2, 7.8], "data_as_of": "2026-05-29"}`.
- On missing cache: returns `{"regime": null, ...}` — frontend renders `"—"` for null values.

---

### 2.3 Learn / Know Page (`learn.html`)

A dedicated page at `/learn` serving as both user guide and course presentation. Sections:

| Anchor | Content |
|---|---|
| `#how-to-use` | Step-by-step: load sample, upload CSV, connect Zerodha MCP |
| `#brokers` | Broker CSV download guide: Zerodha, Groww, Upstox, AngelOne, 5Paisa — collapsible per broker |
| `#zerodha-mcp` | Zerodha MCP server setup (kite-mcp) |
| `#methodology` | VaR (3 methods), ES, HMM, DCC-GARCH, Diebold-Yilmaz, IC — formula + plain-language explanation each |
| `#glossary` | A–Z of all terms used in the dashboard with formula and interpretation |
| `#findings` | Static prose: key findings from the NIFTY 200 Bloomberg analysis. Sub-agent writes structured placeholder text with section headings and formula slots; **user replaces placeholders with actual analysis conclusions from the Bloomberg run.** |
| `#data` | Data provenance: Bloomberg FRTL, tickers, date range, what's gitignored |

All section anchors correspond to tooltip `data-tip` keys so `ⓘ` links land at the right spot.

---

### 2.4 Tooltip System

Every technical term in the dashboard gets an inline `ⓘ` icon. Hovering shows a floating card with a 2–3 sentence explanation and a "Read more →" link to the matching anchor in `/learn`.

**Markup pattern (added throughout `index.html` / `learn.html`):**
```html
<span data-tip="var-historical">Historical VaR <i class="tip-icon">ⓘ</i></span>
```

**`static/data/glossary.json`** — single source of truth for all tooltip content (served at `/static/data/glossary.json`, loaded by `tooltip.js` via `fetch`):
```json
{
  "var-historical": {
    "title": "Historical VaR (99%, 10-day)",
    "summary": "Empirical 99th-percentile loss using non-overlapping 10-day windows. No distribution assumption.",
    "learn": "/learn#glossary"
  },
  "hmm": { ... },
  "diebold-yilmaz": { ... }
}
```

**`tooltip.js`** — loads `glossary.json` once on `DOMContentLoaded`, then attaches `mouseenter`/`mouseleave` to every `[data-tip]` element. Renders a single shared popover div positioned via `getBoundingClientRect`. No per-tooltip DOM nodes.

---

### 2.5 Theme System

No changes to logic — already correct (6 presets, 8 accents, localStorage persistence, CSS variable injection). Work is purely mechanical: move inline `<style>` to `theme.css`, move inline theme JS to `theme.js`.

---

### 2.6 `docs/frontend/code.md`

Claude reads this file for all frontend tasks. It contains:
- The directory tree above (canonical reference)
- Which JS file owns which functionality (one-liner per file)
- CSS variable names and their purpose
- How to add a new dashboard tab (4 steps)
- How to add a new tooltip (2 steps)
- JS load order rationale

`CLAUDE.md` gains one line: `For all frontend changes, read docs/frontend/code.md first.`

---

## 3. Track B — Data Layer

### 3.1 Data Sources

| Data | Source | Coverage |
|---|---|---|
| NSE equities (daily prices + volume) | Bloomberg parquets (backbone) + yfinance `.NS` (gap-fill) | 2018-01-01 → present |
| NSE indices (NIFTY, SENSEX, sectors) | Bloomberg + yfinance `^NSEI`, `^NSEBANK` etc. | 2018 → present |
| Commodities (crude, gold, copper, gas, agri) | Bloomberg + yfinance `CL=F`, `GC=F` etc. | 2018 → present |
| USD/INR | Bloomberg + yfinance `USDINR=X` or FRED `DEXINUS` | 2018 → present |
| India VIX | Bloomberg + yfinance `^NSEIVIX` | 2018 → present |
| India 10Y yield | Bloomberg + FRED (series ID to verify at implementation time; RBI website as fallback) | 2018 → present |
| Annual fundamentals | Bloomberg parquets only (2010–2025); yfinance appends latest year | 2010 → present |

**Bloomberg parquets are never modified.** The gap-fill script only appends new rows to a separate `data/cache/public/` directory. The cache layer merges them at read time (Bloomberg rows take precedence for overlapping dates).

### 3.2 `scripts/pull_public_data.py`

New script alongside the existing `pull_drishti_data.py`. Logic:

1. For each ticker in the Bloomberg registry, read its parquet, find `last_date`.
2. If `today - last_date <= 3 days`: skip (no meaningful gap).
3. Otherwise: fetch `yfinance.download(yahoo_ticker, start=last_date + 1day)`.
4. Map Bloomberg column names → Yahoo column names (`PX_LAST` → `Close`, etc.).
5. Append new rows to `data/cache/public/<category>/<ticker>.parquet`.
6. For macro (10Y yield): call FRED API using `fredapi` with the configured key.
7. For annual fundamentals: fetch `yfinance.Ticker.financials` + `balance_sheet` + `cashflow`; extract the 8 fields matching Bloomberg's `_annual.parquet` schema; append if newer fiscal year exists.

Rate limiting: max 2 requests/second for yfinance. Retry on 429 with exponential backoff. Total runtime for a full refresh: ~10 minutes.

**Bloomberg ticker → Yahoo Finance ticker map** (new file `data/mappings/yahoo_tickers.json`):
```json
{
  "equities": { "HDFCB IN Equity": "HDFCB.NS", "TCS IN Equity": "TCS.NS", ... },
  "indices":  { "NIFTY Index": "^NSEI", "NSEBANK Index": "^NSEBANK", ... },
  "commodities": { "CL1 Comdty": "CL=F", "GC1 Comdty": "GC=F", ... },
  "macro":    { "USDINR Curncy": "USDINR=X", "INVIXN Index": "^NSEIVIX" }
}
```

FRED API key stored in `.env` as `FRED_API_KEY` (`.env.example` updated).

### 3.3 Cache Merge Layer

`src/bloomberg/cache.py` gets a `read_merged(ticker)` method:
1. Read Bloomberg parquet if it exists.
2. Read public parquet if it exists.
3. Concatenate; for duplicate dates Bloomberg rows win.
4. Return merged DataFrame.

All existing callers of `cache.read(ticker)` are unchanged — they call `read_merged()` instead, getting the extended series transparently.

### 3.4 CI/CD — GitHub Actions Weekly

**File:** `.github/workflows/weekly.yml`  
**Schedule:** `cron: '0 2 * * 0'` (Sunday 2 AM UTC)  
**Free tier:** GitHub Actions gives 2000 min/month free for private repos; this job runs ~15 min/week = ~60 min/month — well within limits.

**Steps:**
1. `pip install -r requirements.txt`
2. `python scripts/generate_synthetic_cache.py` — refresh synthetic cache
3. `python scripts/pull_public_data.py` — pull yfinance + FRED gap-fill
4. `PYTHONPATH=. pytest tests/ -v` — run all tests
5. On pass: trigger Render deploy via deploy hook URL (stored as `RENDER_DEPLOY_HOOK` secret)

The public parquet cache (`data/cache/public/`) is committed to the repo (not gitignored — these are small, derived, non-proprietary files). Bloomberg parquets remain gitignored.

### 3.5 Hosting — Render.com

**File:** `render.yaml` at repo root.

```yaml
services:
  - type: web
    name: drishti
    env: python
    buildCommand: pip install -r drishti/requirements.txt
    startCommand: cd drishti && uvicorn src.dashboard.app:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: FRED_API_KEY
        sync: false
```

Free tier: spins down after 15 min idle, ~30s cold start. Acceptable for a course demo. The deployed instance will not have Bloomberg parquets (gitignored) but will have the public cache and synthetic fallback — the static findings page works fully; the interactive analysis works on uploaded CSVs.

---

## 4. What We Explicitly Do NOT Automate

| Item | Reason |
|---|---|
| Bloomberg parquet refresh | FRTL is air-gapped; manual pull required |
| Annual fundamentals history | Bloomberg data (2010–2025) kept as-is |
| LLM-based copilot | No API key required for deterministic memo; LLM is optional extension |
| Real-time prices | This is a risk research tool, not a live trading terminal |

---

## 5. Constraints & Guardrails

- No investment advice language anywhere (existing rule, maintained).
- Bloomberg data files are never committed to the repo.
- The FRED API key is never hardcoded; always read from `.env`.
- All risk functions remain pure (no side effects, no API calls inside `src/risk/` or `src/research/`).
- The `learn.html` glossary explains all metrics but includes the disclaimer: "For educational risk analytics only."
- KaTeX for formula rendering (CDN, free). Falls back gracefully if CDN is unreachable (formula text still readable).

---

## 6. Implementation Order (for sub-agent handoff)

**Task 1 — Frontend overhaul (no backend changes beyond app.py):**
1. Update `app.py`: add `StaticFiles` mount, add Jinja2 setup, add `/learn` route.
2. Create `templates/base.html` with shared header/nav and all CSS/JS imports.
3. Migrate `index.html` → `templates/index.html` (extends base, strips shared markup).
4. Split inline `<style>` → `static/css/` (4 files, load order enforced in base.html).
5. Split inline `<script>` → `static/js/` (9 files, load order enforced in base.html).
6. Create `templates/learn.html` (extends base; all 7 sections with static content).
7. Create `static/data/glossary.json` with all tooltip entries.
8. Create `static/js/tooltip.js`.
9. Add `data-tip` attributes throughout `index.html` on all technical terms.
10. Create `routes/static_data.py` + wire into `app.py`.
11. Create `docs/frontend/code.md`.
12. Update `CLAUDE.md` with pointer to `code.md`.

**Task 2 — Data layer:**
1. Add `yfinance`, `fredapi` to `requirements.txt`.
2. Create `data/mappings/yahoo_tickers.json`.
3. Create `scripts/pull_public_data.py`.
4. Update `src/bloomberg/cache.py` with `read_merged()`.
5. Update `src/bloomberg/cache.py` callers to use `read_merged()`.
6. Update `.env.example` with `FRED_API_KEY`.
7. Create `.github/workflows/weekly.yml`.
8. Create `render.yaml`.
9. Update `drishti/CLAUDE.md` to note the two-cache architecture.

Task 1 and Task 2 are independent — can be executed sequentially by one sub-agent without conflicts.
