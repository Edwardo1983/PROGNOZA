from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer

from ai.orchestrator import AIOrchestrator
from ai_hibrid.pipeline.train import train_pipeline
from app.poll import poll_once

from ..common import console
from ..i18n import t
from .weather import _build_router

system_app = typer.Typer(help="Composed system scenarios")


def _sleep_until(target: float) -> None:
    while True:
        remaining = target - time.time()
        if remaining <= 0:
            break
        time.sleep(min(remaining, 1.0))


@system_app.command("vpn-weather")
def vpn_weather(
    period: int = typer.Option(60, min=10),
    duration: Optional[int] = typer.Option(None),
    config: Optional[Path] = typer.Option(None),
) -> None:
    console().print(t("system.running"))
    router = _build_router(config) if config else None
    stop_event = threading.Event()
    start_time = time.time()

    def poll_thread() -> None:
        next_run = time.time()
        while not stop_event.is_set():
            try:
                poll_once(scheduled_wall_time=next_run)
            except Exception as exc:  # noqa: BLE001
                console().print(f"[red]Polling failed:[/] {exc}")
            next_run += period
            _sleep_until(next_run)
            if duration and (time.time() - start_time) >= duration:
                break

    def weather_thread() -> None:
        if router is None:
            return
        next_run = time.time()
        while not stop_event.is_set():
            try:
                router.get_nowcast(2)
            except Exception as exc:  # noqa: BLE001
                console().print(f"[red]Weather nowcast failed:[/] {exc}")
            next_run += period
            _sleep_until(next_run)
            if duration and (time.time() - start_time) >= duration:
                break

    threads = [
        threading.Thread(target=poll_thread, daemon=True),
        threading.Thread(target=weather_thread, daemon=True),
    ]
    for thread in threads:
        thread.start()

    try:
        if duration:
            _sleep_until(start_time + duration)
            stop_event.set()
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        console().print(t("msgs.shutdown"))
        stop_event.set()

    for thread in threads:
        thread.join(timeout=2)
    console().print(t("system.finished"))


@system_app.command("vpn-weather-train")
def vpn_weather_train(
    period: int = typer.Option(60, min=10),
    collect_for: int = typer.Option(7200, min=60),
    train_cfg: Path = typer.Option(Path("ai_hibrid/config/hybrid.yaml")),
    meas: Path = typer.Option(Path("data/exports/umg_readings_2025-10-13.csv")),
    weather: Path = typer.Option(Path("data/weather/hourly.parquet")),
) -> None:
    console().print(t("system.running"))
    router = _build_router(None)
    start = time.time()
    next_run = time.time()
    try:
        while (time.time() - start) < collect_for:
            scheduled = next_run
            try:
                poll_once(scheduled_wall_time=scheduled)
            except Exception as exc:  # noqa: BLE001
                console().print(f"[red]Polling failed:[/] {exc}")
            try:
                router.get_nowcast(2)
            except Exception as exc:  # noqa: BLE001
                console().print(f"[red]Weather nowcast failed:[/] {exc}")
            next_run += period
            _sleep_until(next_run)
    except KeyboardInterrupt:
        console().print(t("msgs.shutdown"))
        return

    console().print(t("msgs.starting", task="AI Hibrid train"))
    train_pipeline(str(meas), str(weather), str(train_cfg))
    console().print(t("msgs.completed", task="AI Hibrid train"))


@system_app.command("full")
def full(
    nowcast_period: int = typer.Option(300, help="Seconds between nowcast refreshes"),
    hourly_period: int = typer.Option(3600, help="Seconds between hourly updates"),
    quality_period: int = typer.Option(1800, help="Seconds between QA runs"),
    train_period: int = typer.Option(21600, help="Seconds between trainings"),
) -> None:
    console().print(t("system.running"))
    orchestrator = AIOrchestrator()
    router = _build_router(None)
    last_nowcast = last_hourly = last_quality = last_train = 0.0
    try:
        while True:
            now = time.time()
            if now - last_nowcast >= nowcast_period:
                try:
                    router.get_nowcast(2)
                except Exception as exc:  # noqa: BLE001
                    console().print(f"[red]Nowcast error:[/] {exc}")
                last_nowcast = now
            if now - last_hourly >= hourly_period:
                try:
                    start = datetime.utcnow()
                    router.get_hourly(start, start + timedelta(hours=48))
                except Exception as exc:  # noqa: BLE001
                    console().print(f"[red]Hourly error:[/] {exc}")
                last_hourly = now
            if now - last_quality >= quality_period:
                try:
                    from core.data_quality.report import generate_report

                    generate_report(
                        Path("data/exports/umg_readings_2025-10-13.csv"),
                        output_dir=Path("reports/qa"),
                    )
                except Exception as exc:  # noqa: BLE001
                    console().print(f"[yellow]QA warning:[/] {exc}")
                last_quality = now
            if now - last_train >= train_period:
                try:
                    train_pipeline(
                        "data/exports/umg_readings_2025-10-13.csv",
                        "data/weather/hourly.parquet",
                        "ai_hibrid/config/hybrid.yaml",
                    )
                except Exception as exc:  # noqa: BLE001
                    console().print(f"[yellow]Training skipped:[/] {exc}")
                last_train = now
            time.sleep(5)
    except KeyboardInterrupt:
        console().print(t("msgs.shutdown"))
    console().print(t("system.finished"))
