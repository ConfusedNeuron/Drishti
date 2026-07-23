"""FastAPI application entry point."""
import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from src.dashboard.routes import portfolio, risk, research, copilot, frontier
from src.dashboard.routes import static_data

logging.basicConfig(
    level=os.environ.get("DRISHTI_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title="Drishti — Portfolio Risk Analytics",
    description="Local-first quant risk platform for Indian equity portfolios.",
    version="1.0.0",
)

# The dashboard is served same-origin; CORS only matters for external browser
# clients. Set DRISHTI_CORS_ORIGINS="*" (or a comma-separated list) to widen.
_cors_origins = [
    o.strip()
    for o in os.environ.get(
        "DRISHTI_CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(risk.router,      prefix="/api/risk",      tags=["risk"])
app.include_router(research.router,  prefix="/api/research",  tags=["research"])
app.include_router(copilot.router,   prefix="/api/copilot",   tags=["copilot"])
app.include_router(frontier.router,  prefix="/api/frontier",  tags=["frontier"])
app.include_router(static_data.router, tags=["static"])

_STATIC = Path(__file__).parent / "static"
_TEMPLATES = Path(__file__).parent / "templates"
_STATIC.mkdir(exist_ok=True)
_TEMPLATES.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
templates = Jinja2Templates(directory=str(_TEMPLATES))


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/learn")
async def learn(request: Request):
    return templates.TemplateResponse(request, "learn.html")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "drishti"}
