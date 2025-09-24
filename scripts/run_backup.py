"""Ruleaza backup zilnic pentru fisierele critice."""
from __future__ import annotations

from pathlib import Path

from prognoza.config.settings import load_settings
from prognoza.infrastructure.backup import create_backup


def main() -> None:
    settings = load_settings()
    sources = [Path("exports"), Path("config"), Path("prognoza")]
    existing = [path for path in sources if path.exists()]
    if not existing:
        raise FileNotFoundError("Nu exista directoare de backup disponibile")
    archive = create_backup(existing, settings.storage.backup_dir)
    print(f"Backup creat: {archive}")


if __name__ == "__main__":
    main()
