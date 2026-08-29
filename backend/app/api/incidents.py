from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
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


@router.get("/config")
def config():
    s = get_settings()
    return {"agora_app_id": s.agora_app_id, "agora_configured": engine.agora.configured,
            "llm_available": bool(s.llm_api_key), "llm_model": s.llm_model, "demo_mode": s.demo_mode,
            "agent_uid": s.agora_agent_uid}


@router.post("/incidents")
async def create(body: CreateIncident):
    inc = store.create(body.title, body.severity, body.channel or "")
    if not inc.channel:
        inc.channel = f"sentinel-{inc.id.lower()}"
    return inc.model_dump(mode="json")


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
async def join(incident_id: str, body: JoinBody):
    inc = _inc(incident_id)
    store.add_participant(inc, body.uid, body.name, body.role, body.focus)
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
