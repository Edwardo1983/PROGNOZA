"""Centralised settings for the PROGNOZA VPN toolkit."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parents[1]
APP_DIR = BASE_DIR / "app"
DATA_DIR = APP_DIR / "data" / "raw"
EXPORTS_DIR = BASE_DIR / "data" / "exports"
LOG_FILE = DATA_DIR / "vpn.log"
SECRETS_DIR = BASE_DIR / "secrets"

_OVPN_CANDIDATES = (
    SECRETS_DIR / "Prognoza-UMG-509-PRO.ovpn",
    SECRETS_DIR / "eduard.ordean@el-mont.ro-Brezoaia-PT.ovpn",
)

OVPN_INPUT = next((candidate for candidate in _OVPN_CANDIDATES if candidate.exists()), _OVPN_CANDIDATES[0])
OVPN_ASSETS_DIR = SECRETS_DIR / f"{OVPN_INPUT.stem}_assets"
PROFILE_NAME = f"{OVPN_INPUT.stem}-clean"

UMG_IP = "192.168.1.30"
UMG_TCP_PORT = 502
CONNECT_TIMEOUT_S = 90
CONFIG_FILE = BASE_DIR / "config.yaml"


def _ensure_directories(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure a rotating file logger plus console echo."""
    _ensure_directories((DATA_DIR, EXPORTS_DIR, OVPN_ASSETS_DIR))

    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    console_handler = logging.StreamHandler()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[handler, console_handler],
        force=True,
    )


_ensure_directories((DATA_DIR, EXPORTS_DIR, OVPN_ASSETS_DIR))
