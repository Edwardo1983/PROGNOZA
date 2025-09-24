"""Mecanisme de backup si restore pentru fisiere critice."""
from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable


def create_backup(sources: Iterable[Path], destination_dir: Path) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    archive_path = destination_dir / f"backup_{timestamp}.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for source in sources:
            source = source.resolve()
            if source.is_dir():
                for file in source.rglob("*"):
                    if file.is_file():
                        zf.write(file, arcname=file.relative_to(source.parent))
            elif source.is_file():
                zf.write(source, arcname=source.name)
    return archive_path


def restore_backup(archive: Path, target_dir: Path) -> None:
    if not archive.exists():
        raise FileNotFoundError(f"Backup archive not found: {archive}")
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(target_dir)
