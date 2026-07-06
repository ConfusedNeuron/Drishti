"""FastAPI application entry point."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from src.dashboard.routes import portfolio, risk, research, copilot, frontier
from src.dashboard.routes import static_data

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
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/learn")
async def learn(request: Request):
    return templates.TemplateResponse("learn.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok", "service": "drishti"}
