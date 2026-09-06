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
from app.engine.models import now
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
    rid, model = "chatcmpl-" + uuid.uuid4().hex[:12], body.get("model", "sentinel-v1")

    async def gen():
        # First byte goes out IMMEDIATELY — Agora abandons slow LLMs before the
        # first chunk, which silently drops the reply from TTS.
        yield _sse({"id": rid, "object": "chat.completion.chunk", "created": int(time.time()), "model": model,
                    "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]})
        content = ""
        try:
            # tiny wait so the RTM-forwarded copy (with the speaker uid) lands first
            await asyncio.sleep(0.3)
            # RTM already delivered this utterance WITH the speaker's identity in most
            # cases — the anonymous callback copy (which also accumulates turn text)
            # is only a fallback for rooms where no dashboard is forwarding RTM.
            recent_rtm = any(
                l.uid not in ("sentinel", "unknown") and (now() - l.at).total_seconds() < 12
                for l in inc.transcript[-6:]) or bool(engine.pending.get(inc.id))
            if text and not recent_rtm:
                # The callback is anonymous and ACCUMULATES the turn's sentences.
                # 1) keep only sentences we haven't already heard
                import difflib, re as _re
                def _n(t: str) -> str:
                    return _re.sub(r"[^a-z0-9 ]+", "", t.lower()).strip()
                recent = [l.text for l in inc.transcript[-6:] if l.uid != "sentinel"]
                fresh = []
                for sent in _re.split(r"(?<=[.?!।])\s+", text):
                    if len(_n(sent)) < 2:
                        continue
                    if any(difflib.SequenceMatcher(None, _n(sent), _n(r)).ratio() > 0.7 or _n(sent) in _n(r) for r in recent):
                        continue
                    fresh.append(sent)
                # 2) a room with exactly one human isn't anonymous at all
                humans = [p for p in inc.participants.values() if p.uid not in ("sentinel",)]
                uid = humans[0].uid if len(humans) == 1 else (last_user.get("uid") or "unknown")
                if fresh:
                    engine.ingest_transcript(inc, uid, " ".join(fresh), schedule=False)
            speech = await asyncio.wait_for(engine.tick(inc), timeout=12)
            if speech:
                content = speech[0]
                store.sentinel_said(inc, content, speech[1])
                engine.last_spoke[inc.id] = time.time()
        except Exception as e:
            log.warning("llm turn failed: %s", e)
        for i in range(0, len(content), 40):
            yield _sse({"id": rid, "object": "chat.completion.chunk", "created": int(time.time()), "model": model,
                        "choices": [{"index": 0, "delta": {"content": content[i:i + 40]}, "finish_reason": None}]})
        yield _sse({"id": rid, "object": "chat.completion.chunk", "created": int(time.time()), "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})
