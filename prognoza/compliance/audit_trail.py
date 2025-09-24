"""Audit trail pentru trasabilitatea operatiunilor."""
from __future__ import annotations

import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict


class AuditTrail:
    """Gestionare jurnalizare pentru cerinte de audit OTS/ANRE."""

    def __init__(self, log_dir: Path) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger("prognoza.audit")
        self._logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(log_dir / "audit.log", maxBytes=5_000_000, backupCount=10)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        if not self._logger.handlers:
            self._logger.addHandler(handler)

    def record(self, event: str, payload: Dict[str, Any]) -> None:
        entry = {"event": event, "payload": payload}
        self._logger.info(json.dumps(entry, ensure_ascii=False))

    @staticmethod
    def hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()
