from __future__ import annotations

from pathlib import Path

import typer

from .common import console, configure_logging
from .i18n import get_lang, set_lang, t
from .menu import render_menu
from .subapps.ai import ai_app
from .subapps.ai_hibrid import ai_hibrid_app
from .subapps.system import system_app
from .subapps.vpn import vpn_app
from .subapps.weather import weather_app

app = typer.Typer(help="PROGONZA command line interface")
app.add_typer(vpn_app, name="vpn")
app.add_typer(weather_app, name="weather")
app.add_typer(ai_hibrid_app, name="ai-hibrid")
app.add_typer(ai_app, name="ai")
app.add_typer(system_app, name="system")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    configure_logging("cli")
    rc = Path(".progonzarc")
    if not rc.exists():
        choice = typer.prompt(t("prompts.choose_lang"), default="ro")
        lang = choice if choice in {"ro", "en"} else "en"
        set_lang(lang)
        console().print(t("msgs.selected_lang", lang=lang))
    else:
        get_lang()

    if ctx.invoked_subcommand is None:
        menu_options = [
            ("vpn", t("menu.options.vpn")),
            ("weather", t("menu.options.weather")),
            ("ai-hibrid", t("menu.options.ai_hibrid")),
            ("ai", t("menu.options.ai")),
            ("system", t("menu.options.system")),
            ("help", t("menu.options.help")),
        ]
        render_menu(menu_options)
        choice = typer.prompt(t("prompts.menu_choice"), default="").strip().lower()
        if not choice:
            return
        key_map = {
            "1": "vpn",
            "2": "weather",
            "3": "ai-hibrid",
            "4": "ai",
            "5": "system",
            "6": "help",
            "vpn": "vpn",
            "weather": "weather",
            "ai-hibrid": "ai-hibrid",
            "ai": "ai",
            "system": "system",
            "help": "help",
        }
        selected = key_map.get(choice)
        if not selected:
            console().print(t("msgs.error", error=t("msgs.invalid_option")))
            return
        _show_commands(selected)


def _show_commands(selection: str) -> None:
    commands = {
        "vpn": [
            "python -m cli.app vpn status",
            "python -m cli.app vpn connect",
            "python -m cli.app vpn disconnect",
            "python -m cli.app vpn collect-once --out data/raw/umg509/quick_read.csv --regs basic",
        ],
        "weather": [
            "python -m cli.app weather nowcast --hours 2 --out data/weather/nowcast.parquet",
            "python -m cli.app weather hourly --hours 48 --out data/weather/hourly.parquet",
            "python -m cli.app weather export-anre --type intraday --out reports/anre/",
        ],
        "ai-hibrid": [
            "python -m cli.app ai-hibrid train --meas <csv> --weather data/weather/hourly.parquet --cfg ai_hibrid/config/hybrid.yaml --tag run1",
            "python -m cli.app ai-hibrid predict --horizon 48 --weather data/weather/hourly.parquet --out data/forecasts/forecast_48h.csv --model ai_hibrid/models/run1",
            "python -m cli.app ai-hibrid evaluate --meas <recent.csv> --forecast <forecast.csv> --out reports/metrics.json",
        ],
        "ai": [
            "python -m cli.app ai decide --ctx data/context.json",
            "python -m cli.app ai explain --ctx data/context.json --out reports/explain.md",
            "python -m cli.app ai drift --ref data/ref_stats.json --cur data/cur_stats.json --out reports/drift.md",
        ],
        "system": [
            "python -m cli.app system vpn-weather --period 60 --duration 86400",
            "python -m cli.app system vpn-weather --period 60",
            "python -m cli.app system vpn-weather-train --period 60 --collect-for 7200",
            "python -m cli.app system full",
        ],
        "help": [
            "python -m cli.app --help",
            "python -m cli.app <module> --help",
        ],
    }
    console().print(t("msgs.menu_hints"))
    for cmd in commands.get(selection, []):
        console().print(f"  • [cyan]{cmd}[/]")


if __name__ == "__main__":
    app()
