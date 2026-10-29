"""Pløk og Døk: the public website. Presentation only; data comes from db.queries.

Run: uv run uvicorn app.main:app --reload
"""

import json
import os
import random
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import formatting
from db import admin as admin_store
from db import queries

load_dotenv()
HERE = Path(__file__).parent
# Club logos for the front-page wheel: static files, not database data.
CLUB_LOGOS = json.loads((HERE / "static" / "logos" / "logos.json").read_text(encoding="utf-8"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    queries.open_pool()
    yield
    queries.close_pool()
    admin_store.close_pool()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
app.add_middleware(
    SessionMiddleware,
    # Without SESSION_SECRET, logins just don't survive a restart.
    secret_key=os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(48),
    session_cookie="pod_session",
    max_age=8 * 60 * 60,
    same_site="strict",
    https_only=os.environ.get("HTTPS_ONLY") == "1",
)

templates = Jinja2Templates(directory=HERE / "templates")
templates.env.filters.update(formatting.FILTERS)

from app.admin import router as admin_router  # noqa: E402  (needs `templates` above)

app.include_router(admin_router)


def _render(request: Request, name: str, **context) -> HTMLResponse:
    return templates.TemplateResponse(request, name, context)


@app.get("/", response_class=HTMLResponse)
def front_page(request: Request):
    return _render(
        request,
        "index.html",
        competitions=queries.latest_competitions(12),
        totals=queries.site_totals(),
        logos=random.sample(CLUB_LOGOS, len(CLUB_LOGOS)),
    )


@app.get("/sog", response_class=HTMLResponse)
def search(request: Request, q: str = ""):
    """htmx partial: lifter search results under the search box."""
    return _render(request, "partials/search_results.html", q=q, lifters=queries.search_lifters(q))


@app.get("/loefter/{lifter_id}", response_class=HTMLResponse)
def lifter_page(request: Request, lifter_id: int):
    lifter = queries.lifter_summary(lifter_id)
    if lifter is None:
        raise HTTPException(404, "Løfteren findes ikke")
    history = queries.lifter_history(lifter["lifter_id"])
    return _render(
        request,
        "lifter.html",
        lifter=lifter,
        history=history,
        hit_rates=queries.lifter_hit_rates(lifter["lifter_id"]),
        jumps=queries.lifter_favourite_jumps(lifter["lifter_id"]),
        chart=formatting.progression_series(history),
    )


@app.get("/staevne/{competition_id}", response_class=HTMLResponse)
def competition_page(request: Request, competition_id: int):
    comp = queries.competition_summary(competition_id)
    if comp is None:
        raise HTTPException(404, "Stævnet findes ikke")
    return _render(
        request,
        "competition.html",
        comp=comp,
        groups=queries.competition_results(comp["competition_id"]),
        clubs=queries.competition_clubs(comp["competition_id"]),
        top=queries.competition_top_sinclair(comp["competition_id"]),
    )
