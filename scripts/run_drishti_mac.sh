#!/usr/bin/env bash
# ============================================================
#  Drishti — full local run (macOS)
#  Builds every research/risk study artifact, trains the breach
#  classifier, (optionally) refreshes FinBERT news, then launches
#  the dashboard. Assumes the v2 Bloomberg cache is already present.
#
#  Usage:
#    bash scripts/run_drishti_mac.sh                 # build everything + serve
#    SERVE=0 bash scripts/run_drishti_mac.sh         # build only, don't launch server
#    WITH_FINBERT=1 bash scripts/run_drishti_mac.sh  # also install transformers+torch (~2GB) + refresh news
#    INSTALL_DEPS=0 bash scripts/run_drishti_mac.sh  # skip all pip installs
# ============================================================
set -eo pipefail

cd "$(dirname "$0")/.."   # repo root

# ── config (override via env) ──
export DRISHTI_DATA_VERSION="${DRISHTI_DATA_VERSION:-v2}"
export PYTHONPATH="${PYTHONPATH:-.}"
export PYTHONWARNINGS="${PYTHONWARNINGS:-ignore::RuntimeWarning}"   # silence the Diebold-Yilmaz 0/0 noise
SERVE="${SERVE:-1}"
WITH_FINBERT="${WITH_FINBERT:-0}"
INSTALL_DEPS="${INSTALL_DEPS:-1}"

# ── venv ──
if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

step() { echo; echo "════════════════════ $* ════════════════════"; }
echo "Python:        $(command -v python)"
echo "Data version:  $DRISHTI_DATA_VERSION"

# ── deps ──
if [ "$INSTALL_DEPS" = "1" ]; then
  step "Installing breach-classifier dep (xgboost)"
  pip install -q xgboost || echo "WARN: xgboost install failed — breach training will be skipped."
  if [ "$WITH_FINBERT" = "1" ]; then
    step "Installing FinBERT deps (transformers + torch, ~2GB)"
    pip install -q transformers torch || echo "WARN: transformers/torch install failed — news refresh will be skipped."
  fi
fi

# ── research / risk study artifacts ──
step "Spillover study (Diebold-Yilmaz large/mid/combined)"
python scripts/build_spillover_study.py

step "Market shock events study"
python scripts/build_events_study.py

step "Bull/bear regime study"
python scripts/build_regime_study.py

# ── XGBoost breach classifier ──
if python -c "import xgboost" 2>/dev/null; then
  step "Training XGBoost VaR-breach classifier"
  python scripts/train_breach_classifier.py
else
  echo "SKIP: xgboost not available — breach classifier not trained."
fi

# ── FinBERT news sentiment ──
if [ "$WITH_FINBERT" = "1" ] && python -c "import transformers, torch" 2>/dev/null; then
  step "Refreshing FinBERT news sentiment"
  python scripts/news_dry_run.py || echo "WARN: news refresh failed (needs internet)."
else
  echo "SKIP: FinBERT news (run with WITH_FINBERT=1 to enable; needs transformers+torch + internet)."
fi

step "All study artifacts built ✓"

# ── launch dashboard ──
if [ "$SERVE" = "1" ]; then
  step "Launching dashboard → http://localhost:8000  (Ctrl-C to stop)"
  exec uvicorn src.dashboard.app:app --reload
else
  echo "SERVE=0 → not launching. Start the dashboard with:"
  echo "  DRISHTI_DATA_VERSION=$DRISHTI_DATA_VERSION PYTHONPATH=. uvicorn src.dashboard.app:app --reload"
fi
