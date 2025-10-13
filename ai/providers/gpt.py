from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

logger = logging.getLogger(__name__)


class GPTProvider:
    """Wrapper around OpenAI Chat Completions API."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key or OpenAI is None:
            logger.warning("OpenAI provider disabled (missing library or API key).")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key)

    def is_available(self) -> bool:
        return self.client is not None

    def chat(self, system: str, user: str, *, model: Optional[str] = None, temperature: float = 0.3) -> str:
        if not self.is_available():
            raise RuntimeError("OpenAI provider not available")
        model_name = model or self.config.get("model", "gpt-4o-mini")
        response = self.client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
