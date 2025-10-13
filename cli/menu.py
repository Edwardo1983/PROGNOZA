from __future__ import annotations

from typing import Iterable

from rich.panel import Panel
from rich.table import Table

from .common import console
from .i18n import t


def render_menu(options: Iterable[tuple[str, str]]) -> None:
    table = Table()
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Option", style="green")
    for idx, (_, label) in enumerate(options, start=1):
        table.add_row(str(idx), label)
    console().print(Panel(table, title=t("menu.title"), subtitle=t("menu.subtitle")))

