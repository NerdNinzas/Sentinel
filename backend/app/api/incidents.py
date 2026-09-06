from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import auth, db
from app.core.config import get_settings
from fastapi import Depends
from app.core.token import build_tokens
from app.engine import models as m
from app.engine import report
from app.engine.engine import engine
from app.engine.store import store
from app.tools import gateway

router = APIRouter(prefix="/api", tags=["incidents"])


def _inc(incident_id: str) -> m.Incident:
    try:
        return store.get(incident_id)
    except KeyError:
        raise HTTPException(404, "incident not found")


class CreateIncident(BaseModel):
    title: str = "Payment API Outage"
    severity: m.Severity = m.Severity.SEV1
    channel: Optional[str] = None
    repo: Optional[str] = None          # "owner/name"; empty string disables the default


@router.get("/config")
def config():
    s = get_settings()
    return {"agora_app_id": s.agora_app_id, "agora_configured": engine.agora.configured,
            "llm_available": bool(s.llm_api_key), "llm_model": s.llm_model, "demo_mode": s.demo_mode,
            "agent_uid": s.agora_agent_uid,
            "auth_required": s.auth_required, "github_oauth": bool(s.github_oauth_client_id),
            "mongodb": db.available()}


@router.post("/incidents")
async def create(body: CreateIncident, user: dict = Depends(auth.require_user)):
    import asyncio
    inc = store.create(body.title, body.severity, body.channel or "")
    if not inc.channel:
        inc.channel = f"sentinel-{inc.id.lower()}"
    repo = get_settings().github_default_repo if body.repo is None else body.repo
    if repo:
        asyncio.create_task(engine.link_repo(inc, repo, token=user.get("github_token") or None))
    if user.get("_id"):
        asyncio.create_task(db.record_membership(user["_id"], inc.id, "incident_commander", "created"))
    asyncio.create_task(engine.link_jira(inc))
    return inc.model_dump(mode="json")


class RepoBody(BaseModel):
    repo: str


@router.post("/incidents/{incident_id}/repo")
async def set_repo(incident_id: str, body: RepoBody, user: dict = Depends(auth.require_user)):
    inc = _inc(incident_id)
    await engine.link_repo(inc, body.repo.strip(), token=user.get("github_token") or None)
    return {"repo": inc.repo, "changes": inc.repo_changes}


@router.get("/incidents")
def list_incidents():
    return [{"id": i.id, "title": i.title, "severity": i.severity, "status": i.status,
             "started_at": i.started_at, "channel": i.channel, "counts": i.counts()} for i in store.incidents.values()]


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    return _inc(incident_id).model_dump(mode="json")


class JoinBody(BaseModel):
    uid: str
    name: str
    role: m.Role = m.Role.UNKNOWN
    focus: str = ""


@router.post("/incidents/{incident_id}/join")
async def join(incident_id: str, body: JoinBody, user: dict = Depends(auth.require_user)):
    import asyncio
    inc = _inc(incident_id)
    if user.get("_id"):
        body.uid, body.name = user["login"], user.get("name") or user["login"]
        asyncio.create_task(db.record_membership(user["_id"], inc.id, body.role.value, "joined"))
    store.add_participant(inc, body.uid, body.name, body.role, body.focus)
    if inc.agent_id and engine.agora.configured:
        asyncio.create_task(engine.agora.speak(inc.agent_id, f"{body.name} joined the room. Welcome — I am listening."))
    s = get_settings()
    return {"channel": inc.channel, "app_id": s.agora_app_id, "uid": body.uid, "tokens": build_tokens(inc.channel, body.uid)}


class RoleBody(BaseModel):
    role: m.Role
    focus: str = ""


@router.post("/incidents/{incident_id}/participants/{uid}/role")
async def set_role(incident_id: str, uid: str, body: RoleBody):
    inc = _inc(incident_id)
    p = inc.participants.get(uid)
    if not p:
        raise HTTPException(404, "participant not found")
    p.role, p.role_source, p.focus = body.role, "corrected", body.focus or p.focus
    store._timeline(inc, "participant", f"Role corrected: {p.name} → {p.role.value.replace('_', ' ')}", uid)
    store.publish_state(inc)
    return p.model_dump(mode="json")


class TranscriptBody(BaseModel):
    uid: str
    text: str
    final: bool = True
    turn_id: Optional[int] = None


@router.post("/incidents/{incident_id}/transcript")
async def transcript(incident_id: str, body: TranscriptBody):
    """Ingest a transcript line: forwarded Agora RTM `user.transcription`, browser STT, or typed text."""
    inc = _inc(incident_id)
    line = engine.ingest_transcript(inc, body.uid, body.text, body.final, body.turn_id)
    return line.model_dump(mode="json") if line else {}


class DecideBody(BaseModel):
    approve: bool
    by: str


@router.post("/incidents/{incident_id}/proposals/{proposal_id}/decide")
async def decide(incident_id: str, proposal_id: str, body: DecideBody):
    inc = _inc(incident_id)
    prop = await gateway.decide(inc, proposal_id, body.approve, body.by)
    if not prop:
        raise HTTPException(404, "proposal not found")
    if body.approve:
        await engine.say(inc, f"{inc.name_of(body.by)} approved {prop.tool.replace('_', ' ')}. Executing now and watching for recovery.", "SUMMARIZE", "high")
    return prop.model_dump(mode="json")


@router.post("/incidents/{incident_id}/agent/start")
async def agent_start(incident_id: str):
    inc = _inc(incident_id)
    if not engine.agora.configured:
        raise HTTPException(400, "Agora credentials not configured (AGORA_APP_ID / CUSTOMER_KEY / CUSTOMER_SECRET)")
    s = get_settings()
    token = build_tokens(inc.channel, s.agora_agent_uid)["rtc"]
    try:
        return await engine.start_agent(inc, token)
    except Exception as e:
        raise HTTPException(502, f"Agora join failed: {e}")


@router.post("/incidents/{incident_id}/agent/stop")
async def agent_stop(incident_id: str):
    await engine.stop_agent(_inc(incident_id))
    return {"ok": True}


@router.post("/incidents/{incident_id}/demo/start")
async def demo_start(incident_id: str, speed: float = 1.0, auto_approve: bool = False):
    engine.run_scenario(_inc(incident_id), speed=speed, auto_approve=auto_approve)
    return {"ok": True}


@router.post("/incidents/{incident_id}/demo/stop")
async def demo_stop(incident_id: str):
    engine.stop_scenario(_inc(incident_id))
    return {"ok": True}


@router.post("/incidents/{incident_id}/end")
async def end_session(incident_id: str, user: dict = Depends(auth.require_user)):
    """End the war room: stop demo + agent, resolve, persist a final snapshot."""
    inc = _inc(incident_id)
    engine.stop_scenario(inc)
    try:
        await engine.stop_agent(inc)
    except Exception:
        pass
    await engine._apply(inc, [{"op": "set_status", "status": "resolved"}])
    store._timeline(inc, "incident", f"Session ended by {inc.name_of(user.get('login', 'operator'))} — final report available")
    store.publish_state(inc)
    await db.save_incident_now(inc)
    return inc.model_dump(mode="json")


@router.delete("/incidents/{incident_id}")
async def delete_incident(incident_id: str, user: dict = Depends(auth.require_user)):
    """Remove a room entirely (store + Mongo history)."""
    inc = _inc(incident_id)
    engine.stop_scenario(inc)
    try:
        await engine.stop_agent(inc)
    except Exception:
        pass
    store.incidents.pop(incident_id, None)
    if db.available():
        await db.db().incidents.delete_one({"_id": incident_id})
        await db.db().memberships.delete_many({"incident_id": incident_id})
    return {"deleted": incident_id}


@router.post("/incidents/{incident_id}/resolve")
async def resolve(incident_id: str):
    inc = _inc(incident_id)
    await engine._apply(inc, [{"op": "set_status", "status": "resolved"}])
    return inc.model_dump(mode="json")


@router.get("/incidents/{incident_id}/report")
async def get_report(incident_id: str):
    inc = _inc(incident_id)
    return {"markdown": await report.generate(inc)}


@router.get("/incidents/{incident_id}/status-speech")
async def status_speech(incident_id: str):
    return {"text": report.status_speech(_inc(incident_id))}


@router.get("/tools")
def tools():
    return [{"name": t.name, "risk": t.risk, "description": t.description} for t in gateway.REGISTRY.values()]
