from __future__ import annotations

import asyncio
import json
import logging
import socket
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from rich.console import Console
from rich.progress import Progress

from . import APP_ROOT
from .i18n import t

_CONSOLE = Console()
LOG_DIR = APP_ROOT / "logs" / "cli"


def console() -> Console:
    return _CONSOLE


def ensure_dir(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def configure_logging(name: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{name}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


@contextmanager
def jsonl_logger(name: str):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{name}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        def _write(record: Dict[str, Any]) -> None:
            payload = {"timestamp": datetime.utcnow().isoformat() + "Z", **record}
            handle.write(json.dumps(payload) + "\n")
            handle.flush()

        yield _write


async def run_in_executor(func: Callable[..., Any], *args: Any, loop: Optional[asyncio.AbstractEventLoop] = None) -> Any:
    loop = loop or asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: func(*args))


def tcp_check(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class GracefulRunner:
    """Utility to manage background threads/coroutines with graceful shutdown."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    def spawn(self, target: Callable[..., None], *args: Any, name: Optional[str] = None) -> None:
        thread = threading.Thread(target=target, args=args, name=name, daemon=True)
        self._threads.append(thread)
        thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        for thread in self._threads:
            thread.join(timeout=2)

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_event


def progress_task(description: str, total: Optional[int] = None):
    progress = Progress()
    progress.start()
    task_id = progress.add_task(description, total=total)
    return progress, task_id
