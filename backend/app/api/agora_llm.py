"""OpenAI-compatible endpoint that Agora's Conversational AI Engine calls as
the agent's "LLM" (llm.vendor = custom). We don't answer the user's message
directly — we run the incident engine and stream back whatever Sentinel
decided to say (possibly nothing)."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.engine.engine import engine
from app.engine.store import store

router = APIRouter(tags=["agora-llm"])
log = logging.getLogger("sentinel.agora_llm")


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj)}\n\n"


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, authorization: str | None = Header(default=None)):
    s = get_settings()
    if s.sentinel_llm_api_key and authorization != f"Bearer {s.sentinel_llm_api_key}":
        raise HTTPException(401, "bad api key")
    body = await request.json()
    channel = body.get("channel") or (body.get("context") or {}).get("channel")
    inc = store.by_channel(channel) if channel else None
    if inc is None:
        live = [i for i in store.incidents.values() if i.status.value != "resolved"]
        inc = live[-1] if live else None
    if inc is None:
        raise HTTPException(404, "no active incident")

    msgs = body.get("messages", [])
    last_user = next((mm for mm in reversed(msgs) if mm.get("role") == "user"), None)
    text = ""
    if last_user:
        c = last_user.get("content")
        text = c if isinstance(c, str) else " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    # Give the RTM-forwarded transcript (which carries the speaker uid) a moment to land first.
    await asyncio.sleep(0.4)
    if text:
        engine.ingest_transcript(inc, last_user.get("uid") or "unknown", text, schedule=False)
    speech = await engine.tick(inc)
    rid, model = "chatcmpl-" + uuid.uuid4().hex[:12], body.get("model", "sentinel-v1")

    async def gen():
        yield _sse({"id": rid, "object": "chat.completion.custom_metadata", "choices": [],
                    "metadata": {"interruptable": True}})
        content = ""
        if speech:
            content = speech[0]
            store.sentinel_said(inc, content, speech[1])
            engine.last_spoke[inc.id] = time.time()
        for chunk in ([content[i:i + 40] for i in range(0, len(content), 40)] or [""]):
            yield _sse({"id": rid, "object": "chat.completion.chunk", "created": int(time.time()), "model": model,
                        "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}]})
        yield _sse({"id": rid, "object": "chat.completion.chunk", "created": int(time.time()), "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
