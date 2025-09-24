"""CLI pentru operare manuala a sistemului de prognoza."""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

import pandas as pd
import typer

from prognoza.compliance.audit_trail import AuditTrail
from prognoza.compliance.legal_validator import LegalValidator
from prognoza.config.settings import ConfigurationError, Settings, load_settings
from prognoza.data_acquisition.umg_reader import fetch_measurements
from prognoza.infrastructure.vpn import OpenVPNError, create_vpn_manager
from prognoza.processing.aggregator import prepare_notification_series
from prognoza.processing.notification_builder import build_notification
from prognoza.reporting.transelectrica_export import save_csv, save_xml

app = typer.Typer(help="Operatiuni manuale conform procedurilor PRE")

_settings_cache: Optional[Settings] = None
_config_override: Optional[Path] = None


def _resolve_settings_path() -> Optional[Path]:
    if _config_override is not None:
        return _config_override
    env_path = os.getenv("PROGNOZA_CONFIG")
    return Path(env_path) if env_path else None


def get_settings() -> Settings:
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache
    config_path = _resolve_settings_path()
    try:
        _settings_cache = load_settings(config_path)
    except ConfigurationError as exc:
        example = Path("config/settings.example.yaml")
        message = (
            "Configuratie indisponibila: "
            f"{exc}. Seteaza fisierul de configurare prin `--config` sau "
            f"copiaza {example} la `config/settings.yaml`."
        )
        typer.echo(message)
        raise typer.Exit(code=1)
    return _settings_cache


@app.callback()
def main(
    ctx: typer.Context,
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Cale catre fisierul de configurare YAML/JSON pentru sistemul PRE.",
    ),
) -> None:
    global _config_override, _settings_cache
    if config is not None:
        _config_override = config
        _settings_cache = None
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command(name="read_umg")
@app.command(name="read-umg")
def read_umg(
    fields: str = typer.Argument("power_active_total"),
    auto_vpn: bool = typer.Option(
        True,
        help="Porneste automat tunelul OpenVPN inainte de citirea registrelor.",
    ),
    vpn_timeout: int = typer.Option(
        120,
        min=5,
        help="Timp maxim (s) pentru stabilirea tunelului OpenVPN.",
    ),
) -> None:
    """Citeste valori instantanee din UMG 509 PRO."""
    settings = get_settings()

    def _read() -> None:
        try:
            measurement = fetch_measurements(settings.modbus, fields.split(","), settings.umg_http)
        except ConnectionError as exc:
            typer.echo(f"Nu s-a putut citi UMG: {exc}")
            raise typer.Exit(code=3)
        typer.echo(f"Timestamp: {measurement.timestamp.isoformat()}")
        for key, value in measurement.values.items():
            typer.echo(f"{key}: {value:.3f}")

    if auto_vpn and settings.router.openvpn_profile:
        manager = None
        try:
            manager = create_vpn_manager(settings.router, timeout_s=vpn_timeout)
        except OpenVPNError as exc:
            typer.echo(f"Eroare la pregatirea tunelului VPN: {exc}")
            raise typer.Exit(code=2)
        try:
            typer.echo("Pornire tunel OpenVPN...")
            manager.start(timeout_s=vpn_timeout)
            if manager.log_file:
                typer.echo(f"VPN up (log: {manager.log_file})")
            _read()
        except OpenVPNError as exc:
            typer.echo(f"Eroare la pornirea VPN: {exc}")
            if manager.log_file:
                typer.echo(f"Verifica logul: {manager.log_file}")
            raise typer.Exit(code=2)
        finally:
            if manager:
                manager.stop()
    else:
        _read()


@app.command(name="generate_notification")
@app.command(name="generate-notification")
def generate_notification(
    csv_path: Path,
    delivery_day: datetime,
    output_dir: Path = Path("exports"),
) -> None:
    """Genereaza notificare fizica din profil agregat si o salveaza XML/CSV."""
    settings = get_settings()
    df = pd.read_csv(csv_path, parse_dates=[0], index_col=0)
    series = prepare_notification_series(df, delivery_day)
    notification = build_notification(settings.pre, series["planned_mw"])
    output_dir.mkdir(parents=True, exist_ok=True)
    xml_path = output_dir / f"notificare_{delivery_day.strftime('%Y%m%d')}.xml"
    csv_path_out = output_dir / f"notificare_{delivery_day.strftime('%Y%m%d')}.csv"
    save_xml(notification, xml_path)
    save_csv(notification, csv_path_out, unit_id="UMG509")
    audit = AuditTrail(output_dir)
    audit.record("notification_generated", {"xml": str(xml_path), "csv": str(csv_path_out)})
    typer.echo(f"Exportate: {xml_path} si {csv_path_out}")


@app.command(name="validate_notification")
@app.command(name="validate-notification")
def validate_notification(xml_file: Path) -> None:
    """Ruleaza verificari legale pe o notificare existenta."""
    settings = get_settings()
    validator = LegalValidator(settings.pre, settings.quality, settings.deadlines)
    from lxml import etree

    tree = etree.parse(str(xml_file))
    intervals = []
    for interval in tree.xpath("//Interval"):
        start = pd.Timestamp(interval.findtext("Start"))
        end = pd.Timestamp(interval.findtext("End"))
        power = float(interval.findtext("Putere"))
        intervals.append((start, end, power))
    series = pd.Series({item[0]: item[2] for item in intervals})
    series.index = series.index.tz_localize(settings.pre.timezone)
    notification = build_notification(settings.pre, series)
    issues = validator.validate_notification(notification)
    if not issues:
        typer.echo("Notificare conforma")
    else:
        for issue in issues:
            typer.echo(f"{issue.severity.upper()}: {issue.message}")


if __name__ == "__main__":
    app()
