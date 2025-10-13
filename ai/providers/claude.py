from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None

logger = logging.getLogger(__name__)


class ClaudeProvider:
    """Wrapper around Anthropic Claude API."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic is None or not api_key:
            logger.info("Anthropic provider disabled (missing library or key).")
            self.client = None
        else:
            self.client = anthropic.Anthropic(api_key=api_key)

    def is_available(self) -> bool:
        return self.client is not None

    def chat(self, system: str, user: str, *, model: Optional[str] = None, temperature: float = 0.4) -> str:
        if not self.is_available():
            raise RuntimeError("Anthropic provider not available")
        model_name = model or self.config.get("model", "claude-3-haiku-20240307")
        message = self.client.messages.create(
            model=model_name,
            system=system,
            max_tokens=self.config.get("max_tokens", 512),
            temperature=temperature,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in message.output_text) if hasattr(message, "output_text") else message.content[0]["text"]
