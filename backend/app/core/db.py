"""MongoDB persistence (Atlas). Everything degrades gracefully: if Mongo is
unreachable, Sentinel keeps working from the in-memory store."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings

log = logging.getLogger("sentinel.db")

_client: Optional[AsyncIOMotorClient] = None
_ok = False


def db():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(get_settings().mongodb_url, serverSelectionTimeoutMS=6000)
    return _client.get_database("Sentinel")


def available() -> bool:
    return _ok and bool(get_settings().mongodb_url)


async def connect() -> bool:
    global _ok
    if not get_settings().mongodb_url:
        log.warning("MONGODB_URL not set — persistence disabled")
        return False
    try:
        await db().command("ping")
        _ok = True
        log.info("MongoDB connected")
        await db().sessions.create_index("user_id")
        await db().memberships.create_index([("user_id", 1), ("last_seen", -1)])
        return True
    except Exception as e:
        log.error("MongoDB unreachable, running memory-only: %s", e)
        _ok = False
        return False


def now() -> datetime:
    return datetime.now(timezone.utc)


# ---- users & sessions ------------------------------------------------------
async def upsert_user(gh_user: dict[str, Any], token: str) -> dict[str, Any]:
    doc = {
        "_id": gh_user["id"], "login": gh_user["login"], "name": gh_user.get("name") or gh_user["login"],
        "avatar_url": gh_user.get("avatar_url"), "html_url": gh_user.get("html_url"),
        "github_token": token,          # hackathon scope: plaintext; encrypt before production
        "updated_at": now(),
    }
    if available():
        await db().users.update_one({"_id": doc["_id"]}, {"$set": doc, "$setOnInsert": {"created_at": now()}}, upsert=True)
    return doc


async def create_session(user_id: int, token: str) -> None:
    if available():
        await db().sessions.insert_one({"_id": token, "user_id": user_id, "created_at": now()})


async def get_session_user(token: str) -> Optional[dict[str, Any]]:
    if not available():
        return None
    s = await db().sessions.find_one({"_id": token})
    if not s:
        return None
    return await db().users.find_one({"_id": s["user_id"]})


async def delete_session(token: str) -> None:
    if available():
        await db().sessions.delete_one({"_id": token})


# ---- rooms / memberships ---------------------------------------------------
async def record_membership(user_id: int, incident_id: str, role: str, kind: str) -> None:
    if available():
        await db().memberships.update_one(
            {"user_id": user_id, "incident_id": incident_id},
            {"$set": {"role": role, "last_seen": now()}, "$setOnInsert": {"kind": kind, "joined_at": now()}},
            upsert=True)


async def user_rooms(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    if not available():
        return []
    cur = db().memberships.find({"user_id": user_id}).sort("last_seen", -1).limit(limit)
    return [{k: v for k, v in m.items() if k != "_id"} async for m in cur]


# ---- incident snapshots ----------------------------------------------------
_dirty: set[str] = set()
_flush_task: Optional[asyncio.Task] = None


def mark_dirty(incident_id: str) -> None:
    """Write-behind: coalesce state writes, flush every 2s."""
    global _flush_task
    if not available():
        return
    _dirty.add(incident_id)
    loop = asyncio.get_event_loop()
    if _flush_task is None or _flush_task.done():
        _flush_task = loop.create_task(_flush())


async def _flush() -> None:
    await asyncio.sleep(2)
    from app.engine.store import store
    ids, _dirty_copy = list(_dirty), _dirty.clear()
    for iid in ids:
        inc = store.incidents.get(iid)
        if not inc:
            continue
        try:
            await db().incidents.update_one({"_id": iid}, {"$set": {"state": inc.model_dump(mode="json"), "saved_at": now()}}, upsert=True)
        except Exception as e:
            log.warning("incident save failed %s: %s", iid, e)


async def save_incident_now(inc) -> None:
    if available():
        await db().incidents.update_one({"_id": inc.id}, {"$set": {"state": inc.model_dump(mode="json"), "saved_at": now()}}, upsert=True)


async def load_incidents(limit: int = 25) -> list[dict[str, Any]]:
    if not available():
        return []
    cur = db().incidents.find({}).sort("saved_at", -1).limit(limit)
    return [d["state"] async for d in cur]
