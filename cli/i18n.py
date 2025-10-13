from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from . import LOCALES_DIR, RC_FILE

_CACHE: Dict[str, Dict[str, str]] = {}
_LANG: Optional[str] = None


def _load_language(lang: str) -> Dict[str, str]:
    if lang in _CACHE:
        return _CACHE[lang]
    path = LOCALES_DIR / f"{lang}.json"
    if not path.exists():
        if lang != "en":
            return _load_language("en")
        return {}
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    _CACHE[lang] = data
    return data


def get_lang(default: str = "en") -> str:
    global _LANG  # noqa: PLW0603
    if _LANG:
        return _LANG
    if RC_FILE.exists():
        try:
            with RC_FILE.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
                lang = data.get("lang")
                if isinstance(lang, str):
                    _LANG = lang
                    return lang
        except json.JSONDecodeError:
            pass
    _LANG = default
    return _LANG


def set_lang(lang: str) -> None:
    global _LANG  # noqa: PLW0603
    _LANG = lang
    RC_FILE.write_text(json.dumps({"lang": lang}, indent=2), encoding="utf-8")


def t(key: str, **fmt) -> str:
    lang = get_lang()
    catalog = _load_language(lang)
    if key not in catalog and lang != "en":
        catalog = _load_language("en")
    value = catalog.get(key, key)
    if fmt:
        try:
            value = value.format(**fmt)
        except Exception:  # pragma: no cover - defensive
            pass
    return value
