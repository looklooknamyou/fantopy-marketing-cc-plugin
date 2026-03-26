"""
Shared Anthropic Claude client for all marketing agents.
"""

import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. See CREDENTIALS.md."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def ask(system: str, user: str, max_tokens: int = 1024) -> str:
    """Single-turn LLM call. Returns text response."""
    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text.strip()
