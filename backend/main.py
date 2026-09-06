from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agora_llm, auth as auth_api, incidents, ws
from app.core import db
from app.engine import models as _m
from app.engine.store import store
from app.engine.engine import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    for state in await db.load_incidents():
        try:
            inc = _m.Incident.model_validate(state)
            store.incidents.setdefault(inc.id, inc)
        except Exception as e:
            logging.getLogger("sentinel").warning("rehydrate failed: %s", e)
    await engine.start()
    yield
    await engine.stop()


app = FastAPI(title="Sentinel — AI Incident Commander", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(incidents.router)
app.include_router(auth_api.router)
app.include_router(agora_llm.router)
app.include_router(ws.router)


@app.get("/health")
def health():
    return {"ok": True}
