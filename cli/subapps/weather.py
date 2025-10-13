from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import typer

from weather.router import WeatherRouter, build_providers, load_weather_config

from ..common import console, ensure_dir
from ..i18n import t

weather_app = typer.Typer(help="Weather data utilities")


def _build_router(config_path: Optional[Path]) -> WeatherRouter:
    config = load_weather_config(config_path)
    providers = build_providers(config)
    if not providers:
        raise RuntimeError("No weather providers configured.")
    return WeatherRouter(providers, tz=config.get("timezone", "UTC"))


@weather_app.command("nowcast")
def nowcast(
    hours: int = typer.Option(2, min=1, max=6),
    out: Path = typer.Option(Path("data/weather/nowcast.parquet")),
    config: Optional[Path] = typer.Option(None, help="Optional weather config override"),
) -> None:
    router = _build_router(config)
    frame = router.get_nowcast(hours)
    ensure_dir(out)
    frame.to_parquet(out)
    console().print(t("weather.saved", path=str(out)))


@weather_app.command("hourly")
def hourly(
    hours: int = typer.Option(48, min=1, max=168),
    out: Path = typer.Option(Path("data/weather/hourly.parquet")),
    config: Optional[Path] = typer.Option(None),
) -> None:
    router = _build_router(config)
    now = datetime.utcnow()
    horizon = now + timedelta(hours=hours)
    frame = router.get_hourly(now, horizon)
    ensure_dir(out)
    frame.to_parquet(out)
    console().print(t("weather.saved", path=str(out)))


@weather_app.command("export-anre")
def export_anre(
    type: str = typer.Option("intraday", "--type", help="intraday or dayahead"),
    out: Path = typer.Option(Path("reports/anre")),
    source: Path = typer.Option(Path("data/weather/hourly.parquet")),
) -> None:
    if type not in {"intraday", "dayahead"}:
        raise typer.BadParameter("type must be intraday or dayahead")
    if not source.exists():
        raise typer.BadParameter(f"Weather source {source} not found; run weather hourly first.")
    df = pd.read_parquet(source)
    df = df.sort_index()
    horizon_hours = 24 if type == "intraday" else 48
    start = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=horizon_hours)
    sliced = df.loc[(df.index >= start) & (df.index < end)]
    if sliced.empty:
        raise RuntimeError("No data available for requested horizon")

    export_dir = out / datetime.utcnow().date().isoformat()
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / f"weather_{type}.csv"
    sliced.reset_index().rename(columns={"timestamp": "datetime"}).to_csv(export_path, index=False)
    console().print(f"[green]{export_path}[/] ready with {len(sliced)} rows")
