from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.engine.store import store

router = APIRouter()
log = logging.getLogger("sentinel.ws")


@router.websocket("/ws/incidents/{incident_id}")
async def incident_ws(ws: WebSocket, incident_id: str):
    await ws.accept()
    try:
        inc = store.get(incident_id)
    except KeyError:
        await ws.close(code=4004)
        return
    q = store.subscribe(incident_id)
    await ws.send_json({"type": "state", "incident": inc.model_dump(mode="json")})
    await ws.send_json({"type": "transcript_bulk", "lines": [l.model_dump(mode="json") for l in inc.transcript]})

    async def pump():
        while True:
            msg = await q.get()
            await ws.send_json(msg)

    task = asyncio.create_task(pump())
    try:
        while True:
            await ws.receive_text()   # client pings; ignore content
    except WebSocketDisconnect:
        pass
    finally:
        task.cancel()
        store.unsubscribe(incident_id, q)
