from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import typer
from rich.table import Table

from app.janitza_client import DEFAULT_REGISTERS, JanitzaUMG, load_umg_config
from app.vpn_connection import VPNConnection

from ..common import console, ensure_dir
from ..i18n import t

vpn_app = typer.Typer(help="VPN control commands")

_CHECK_TARGETS = [("192.168.1.30", 502), ("192.168.1.30", 80)]

_REG_PRESETS: Dict[str, List[str]] = {
    "basic": [
        "power_active_total",
        "power_reactive_total",
        "power_apparent_total",
        "frequency",
        "power_factor",
    ],
    "quality": [
        "thd_voltage_l1",
        "thd_current_l1",
        "voltage_l1",
        "voltage_l2",
        "voltage_l3",
        "current_l1",
        "current_l2",
        "current_l3",
    ],
    "energy": [
        "energy_active_import_total",
        "energy_active_export_total",
        "energy_reactive_total_sum",
        "energy_export_global_total",
    ],
}


def _check_tcp(host: str, port: int) -> bool:
    try:
        from socket import create_connection

        with create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


@vpn_app.command("status")
def status() -> None:
    vpn = VPNConnection()
    info = vpn.status()
    table = Table(title=t("menu.options.vpn"))
    table.add_column("Field")
    table.add_column("Value")
    for key, value in info.items():
        table.add_row(str(key), json.dumps(value, default=str))
    console().print(table)

    for host, port in _CHECK_TARGETS:
        reachable = _check_tcp(host, port)
        label = f"{host}:{port}"
        status_text = "[green]OK[/]" if reachable else "[red]FAIL[/]"
        console().print(f"[bold]{label}[/] {status_text}")


@vpn_app.command("connect")
def connect() -> None:
    vpn = VPNConnection()
    console().print(t("msgs.starting", task="VPN connect"))
    result = vpn.connect()
    console().print(json.dumps(result, indent=2, default=str))


@vpn_app.command("disconnect")
def disconnect() -> None:
    vpn = VPNConnection()
    console().print(t("msgs.starting", task="VPN disconnect"))
    vpn.disconnect()
    console().print(t("msgs.completed", task="VPN"))


@vpn_app.command("collect-once")
def collect_once(
    out: Path = typer.Option(Path("data/raw/umg509/quick_read.csv")),
    regs: str = typer.Option("basic", help="Preset of registers to read"),
) -> None:
    preset = _REG_PRESETS.get(regs)
    if not preset:
        raise typer.BadParameter(f"Unknown preset {regs}")

    vpn = VPNConnection()
    status_info = vpn.status()
    started = False
    if not status_info.get("is_connected"):
        result = vpn.connect()
        if not result.get("is_connected"):
            raise typer.Exit(code=1)
        started = True

    try:
        umg_cfg = load_umg_config()
        registers = {name: DEFAULT_REGISTERS[name] for name in preset if name in DEFAULT_REGISTERS}
        umg_cfg["registers"] = registers
        client = JanitzaUMG(**umg_cfg)
        readings = client.read_registers()
        row = {key: readings.get(key) for key in registers}
        row["timestamp"] = datetime.now().isoformat()
        out = ensure_dir(out)
        exists = out.exists()
        with out.open("a", encoding="utf-8") as handle:
            if not exists:
                handle.write(",".join(row.keys()) + "\n")
            handle.write(",".join(str(row[k]) for k in row.keys()) + "\n")
        console().print(t("vpn.collect.done", path=str(out)))
    finally:
        if started:
            vpn.disconnect()
