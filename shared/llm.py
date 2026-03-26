"""
Shared LLM client for all marketing agents.
Provider priority: GROQ_API_KEY → GEMINI_API_KEY → error.
Gemini (aistudio.google.com) is free with a Google account, no card required.
"""

import os
from dotenv import load_dotenv

load_dotenv()

_client = None
_provider = None


def _get_client():
    global _client, _provider
    if _client is not None:
        return _client, _provider

    groq_key = os.environ.get("GROQ_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")

    if groq_key:
        from groq import Groq
        _client = Groq(api_key=groq_key)
        _provider = "groq"
    elif gemini_key:
        import google.generativeai as genai
        genai.configure(api_key=gemini_key)
        _client = genai
        _provider = "gemini"
    else:
        raise RuntimeError(
            "No LLM key found. Set GROQ_API_KEY (console.groq.com, free) "
            "or GEMINI_API_KEY (aistudio.google.com, free) in .env"
        )

    return _client, _provider


def ask(system: str, user: str, max_tokens: int = 1024) -> str:
    """Single-turn LLM call. Returns text response."""
    client, provider = _get_client()

    if provider == "groq":
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content.strip()

    elif provider == "gemini":
        model = client.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=system,
        )
        response = model.generate_content(
            user,
            generation_config={"max_output_tokens": max_tokens},
        )
        return response.text.strip()
