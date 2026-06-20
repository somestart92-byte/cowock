"""Thin wrapper around the Anthropic API with an offline fallback.

If ANTHROPIC_API_KEY is set and the `anthropic` package is installed, real
calls are made. Otherwise the agent runs in DRY-RUN mode and emits clearly
labelled placeholder text, so the whole pipeline is testable with no key.
"""

from __future__ import annotations

import os
from typing import Any

try:  # optional dependency
    import anthropic  # type: ignore
except Exception:  # pragma: no cover - import guard
    anthropic = None  # type: ignore


class LLM:
    def __init__(self, model: str, max_tokens: int = 4000, temperature: float = 0.7):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.dry_run = not (self.api_key and anthropic is not None)
        self._client = (
            anthropic.Anthropic(api_key=self.api_key) if not self.dry_run else None
        )

    def complete(self, system: str, prompt: str, **overrides: Any) -> str:
        """Return model text for a single-turn request."""
        if self.dry_run:
            return self._placeholder(system, prompt)

        resp = self._client.messages.create(  # type: ignore[union-attr]
            model=overrides.get("model", self.model),
            max_tokens=overrides.get("max_tokens", self.max_tokens),
            temperature=overrides.get("temperature", self.temperature),
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        ).strip()

    @staticmethod
    def _placeholder(system: str, prompt: str) -> str:
        head = prompt.strip().splitlines()[0][:120] if prompt.strip() else "(empty)"
        return (
            "[DRY-RUN OUTPUT — no ANTHROPIC_API_KEY set]\n"
            f"Task: {head}\n\n"
            "Set ANTHROPIC_API_KEY and install `anthropic` to generate real content. "
            "The pipeline, files, and approval flow all work; only the text is mocked."
        )
