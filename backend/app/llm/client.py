"""LLM access. OpenAI-compatible so it works with OpenAI, Gemini (OpenAI compat
endpoint), Groq, OpenRouter, Ollama. If no key is configured, callers fall back
to the rule-based extractor so the demo never hard-depends on network."""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from openai import AsyncOpenAI

from app.core.config import get_settings

log = logging.getLogger("sentinel.llm")

_client: Optional[AsyncOpenAI] = None


def available() -> bool:
    return bool(get_settings().llm_api_key)


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        s = get_settings()
        _client = AsyncOpenAI(base_url=s.llm_base_url, api_key=s.llm_api_key or "none")
    return _client


async def complete_json(system: str, user: str, temperature: float = 0.1) -> dict[str, Any]:
    s = get_settings()
    resp = await client().chat.completions.create(
        model=s.llm_model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    text = resp.choices[0].message.content or "{}"
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # tolerate ```json fences
        text = text.strip().strip("`")
        if text.startswith("json"):
            text = text[4:]
        return json.loads(text)


async def complete_text(system: str, user: str, temperature: float = 0.3) -> str:
    s = get_settings()
    resp = await client().chat.completions.create(
        model=s.llm_model, temperature=temperature,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return resp.choices[0].message.content or ""
