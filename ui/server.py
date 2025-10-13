"""FastAPI application serving the PROGONZA dashboard UI."""

from __future__ import annotations

import asyncio
import json
import logging
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dateutil import parser
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from uvicorn import Config, Server

from . import APP_ROOT
from .data_access import list_weather_files, load_janitza_latest, load_janitza_series, load_weather_series, discover_metric_columns
from .schemas import SeriesResponse

LOGGER = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)

router = APIRouter()


def parse_iso(dt_str: Optional[str], default: Optional[datetime] = None) -> datetime:
    if dt_str:
        return parser.isoparse(dt_str).astimezone()
    if default:
        return default
    return datetime.now().astimezone()


def render_template(name: str, **context) -> HTMLResponse:
    template = jinja_env.get_template(name)
    return HTMLResponse(template.render(**context))


def available_metrics() -> List[str]:
    return discover_metric_columns()


@router.get("/ui", response_class=HTMLResponse)
async def ui_index(request: Request) -> HTMLResponse:
    context = {
        "request": request,
        "metrics": available_metrics(),
        "weather_options": list_weather_files().keys(),
    }
    return render_template("index.html", **context)


@router.get("/ui/controls", response_class=HTMLResponse)
async def ui_controls(
    request: Request,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> HTMLResponse:
    start_dt = parse_iso(start)
    end_dt = parse_iso(end, default=datetime.now().astimezone())
    context = {
        "request": request,
        "start": start_dt,
        "end": end_dt,
        "metrics": available_metrics(),
        "weather_options": list(list_weather_files().keys()),
    }
    return render_template("_controls.html", **context)


@router.get("/ui/api/janitza", response_class=JSONResponse)
async def api_janitza(
    start: str = Query(...),
    end: str = Query(...),
    metrics: str = Query(""),
) -> JSONResponse:
    metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
    if not metric_list:
        return JSONResponse({"series": [], "meta": {}})
    start_dt = parse_iso(start)
    end_dt = parse_iso(end)
    payload = load_janitza_series(start_dt.astimezone(), end_dt.astimezone(), metric_list)
    return JSONResponse(payload.model_dump())


@router.get("/ui/janitza/table", response_class=HTMLResponse)
async def janitza_table(
    request: Request,
    start: str = Query(...),
    end: str = Query(...),
    metrics: str = Query(""),
) -> HTMLResponse:
    metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
    start_dt = parse_iso(start)
    end_dt = parse_iso(end)
    rows = load_janitza_latest(start_dt.astimezone(), end_dt.astimezone(), metric_list)
    return render_template("_janitza_table.html", request=request, rows=rows)


@router.get("/ui/api/weather", response_class=JSONResponse)
async def api_weather(
    type: str = Query(..., alias="type"),
    start: str = Query(...),
    end: str = Query(...),
) -> JSONResponse:
    start_dt = parse_iso(start)
    end_dt = parse_iso(end)
    payload = load_weather_series(type, start_dt.astimezone(), end_dt.astimezone())
    return JSONResponse(payload.model_dump())


app = FastAPI(title="PROGONZA UI")
app.mount("/ui/static", StaticFiles(directory=STATIC_DIR), name="ui-static")
app.include_router(router)


@app.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/ui")


def start_ui(host: str, port: int, open_browser: bool = True) -> None:
    """Start the FastAPI UI server via uvicorn."""

    config = Config(app=app, host=host, port=port, log_level="info")
    server = Server(config=config)

    if open_browser:
        url = f"http://{host}:{port}/ui"

        def _open() -> None:
            webbrowser.open(url)

        asyncio.get_event_loop().call_later(1.0, _open)

    asyncio.run(server.serve())
