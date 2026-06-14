@echo off
REM ============================================================
REM  Drishti v2 + v3 (OHLC) Bloomberg pull runbook
REM  RUN AT FRTL (the Bloomberg terminal, Windows) ONLY.
REM  Requires a live Bloomberg / BLPAPI session.
REM  Runs all steps back-to-back; the equities pull is ~60 min
REM  but resumable (re-run safely if interrupted).
REM ============================================================

cd /d C:\Users\User\Pranav\drishti
call .venv\Scripts\activate.bat

echo.
echo ============================================================
echo  STEP 1: v2 data pull (pull_drishti_v2.py)
echo ============================================================
echo.

echo [1.1] validate -- field/ticker sanity, no big pulls
python scripts\pull_drishti_v2.py --validate

echo [1.2] discover -- index membership to universe_v2.json (needed by equities/sectors/OHLC)
python scripts\pull_drishti_v2.py --discover

echo [1.3] indices + commodities + macro -- fast groups
python scripts\pull_drishti_v2.py --indices --commodities --macro

echo [1.4] equities -- the big one (433 names)
python scripts\pull_drishti_v2.py --equities

echo [1.5] sectors -- GICS sector for whole universe
python scripts\pull_drishti_v2.py --sectors

echo [1.6] annual -- optional fundamentals (Altman/credit need these)
python scripts\pull_drishti_v2.py --annual

echo [1.7] retry-failed -- re-attempt anything in the failure log
python scripts\pull_drishti_v2.py --retry-failed

REM --- If FRTL entitlements are limited, comment out STEP 1 above and
REM --- use the fallback variant instead (uncomment the two lines below):
REM python scripts\pull_drishti_v2_fallback.py --discover --with-fallbacks
REM python scripts\pull_drishti_v2_fallback.py --indices --commodities --macro --equities --sectors

echo.
echo ============================================================
echo  STEP 2: v3 OHLC pull (pull_ohlc_frtl.py)
echo  Needs universe_v2.json from STEP 1.
echo ============================================================
echo.

echo [2.1] validate -- 5-day field sanity
python scripts\pull_ohlc_frtl.py --validate

echo [2.2] indices + commodities
python scripts\pull_ohlc_frtl.py --indices --commodities

echo [2.3] equities -- all 433 from the v2 manifest
python scripts\pull_ohlc_frtl.py --equities

echo [2.4] retry-failed
python scripts\pull_ohlc_frtl.py --retry-failed

echo.
echo ============================================================
echo  DONE.
echo  Now copy data\cache\bloomberg_v2\ (including the ohlc\ subtree)
echo  to the Mac at data/cache/bloomberg_v2/, then run:
echo    PYTHONPATH=. python scripts/verify_v2_cache.py
echo ============================================================
pause
