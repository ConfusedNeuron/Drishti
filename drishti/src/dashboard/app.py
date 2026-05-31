"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path

from src.dashboard.routes import portfolio, risk, research, copilot

app = FastAPI(
    title="Drishti — Portfolio Risk Analytics",
    description="Local-first quant risk platform for Indian equity portfolios.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(risk.router,      prefix="/api/risk",      tags=["risk"])
app.include_router(research.router,  prefix="/api/research",  tags=["research"])
app.include_router(copilot.router,   prefix="/api/copilot",   tags=["copilot"])

# Serve frontend HTML
_STATIC = Path(__file__).parent / "static"
_STATIC.mkdir(exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def root():
    html_file = _STATIC / "index.html"
    if html_file.exists():
        return HTMLResponse(html_file.read_text())
    return HTMLResponse("<h1>Drishti starting…</h1><p>Run the build to generate frontend.</p>")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "drishti"}
