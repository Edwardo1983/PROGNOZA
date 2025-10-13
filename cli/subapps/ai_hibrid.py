from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import typer

from ai_hibrid.pipeline.train import train_pipeline
from ai_hibrid.pipeline.predict import predict_pipeline
from ai_hibrid.metrics.eval import evaluate_metrics

from ..common import console, ensure_dir
from ..i18n import t

ai_hibrid_app = typer.Typer(help="AI Hibrid training and prediction")


@ai_hibrid_app.command("train")
def train(
    meas: Path = typer.Option(..., exists=True),
    weather: Path = typer.Option(..., exists=True),
    cfg: Path = typer.Option(Path("ai_hibrid/config/hybrid.yaml")),
    tag: str = typer.Option("default"),
) -> None:
    artifact_root = Path("ai_hibrid/models") / tag
    console().print(t("msgs.starting", task=f"AI Hibrid train ({tag})"))
    metrics = train_pipeline(
        str(meas),
        str(weather),
        str(cfg),
        artifact_root=artifact_root,
    )
    console().print(metrics)
    console().print(t("msgs.completed", task="train"))


@ai_hibrid_app.command("predict")
def predict(
    horizon: int = typer.Option(48, min=1),
    weather: Path = typer.Option(..., exists=True),
    out: Path = typer.Option(Path("data/forecasts/forecast.csv")),
    model_dir: Path = typer.Option(Path("ai_hibrid/models/default")),
    cfg: Path = typer.Option(Path("ai_hibrid/config/hybrid.yaml")),
) -> None:
    out = ensure_dir(out)
    metrics = predict_pipeline(
        str(weather),
        str(cfg),
        horizon=horizon,
        out_path=str(out),
        artifact_root=model_dir,
    )
    console().print(t("msgs.completed", task="predict"))
    if metrics:
        console().print(metrics)


@ai_hibrid_app.command("evaluate")
def evaluate(
    meas: Path = typer.Option(..., exists=True),
    forecast: Path = typer.Option(..., exists=True),
    out: Path = typer.Option(Path("reports/metrics.json")),
) -> None:
    actuals = pd.read_csv(meas)
    forecast_df = pd.read_csv(forecast)
    if "timestamp" not in actuals.columns or "power_W" not in actuals.columns:
        raise typer.BadParameter("Measurement CSV must include timestamp and power_W")
    common = actuals.merge(forecast_df, on="timestamp")
    metrics = evaluate_metrics(common["power_W"], common.filter(like="forecast_power").iloc[:, 0])
    out = ensure_dir(out)
    out.write_text(pd.Series(metrics).to_json(), encoding="utf-8")
    console().print(t("msgs.completed", task="evaluate"))
