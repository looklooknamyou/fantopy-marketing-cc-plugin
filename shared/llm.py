"""
Shared Anthropic Claude client for all marketing agents.
"""

import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
if not _api_key:
    raise RuntimeError("ANTHROPIC_API_KEY is not set. See CREDENTIALS.md.")
client = anthropic.Anthropic(api_key=_api_key)

MODEL = "claude-sonnet-4-6"


def ask(system: str, user: str, max_tokens: int = 1024) -> str:
    """Single-turn LLM call. Returns text response."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text.strip()
