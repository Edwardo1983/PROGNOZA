from __future__ import annotations

import asyncio
import typer

from ..common import console
from ..i18n import t

ui_app = typer.Typer(help="Launch the PROGONZA dashboard UI")


@ui_app.command("start")
def start_ui(
    host: str = typer.Option("127.0.0.1", "--host", "-h"),
    port: int = typer.Option(8090, "--port", "-p"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser automatically"),
) -> None:
    """Start the lightweight FastAPI dashboard."""
    from ui.server import start_ui as run_server

    console().print(t("msgs.starting", task="UI server"))

    try:
        run_server(host, port, open_browser=open_browser)
    except KeyboardInterrupt:
        console().print(t("msgs.shutdown"))
