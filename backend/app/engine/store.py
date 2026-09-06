"""In-memory incident store + event bus.

Every mutation goes through `apply_ops`, bumps `incident.version`, appends
timeline events, and broadcasts the new state to WebSocket subscribers.
Persistence to SQLite is a thin snapshot (see persistence.py) so the demo
stays fast and the state is always the single source of truth.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

from app.core import db as _db
from app.engine import models as m

log = logging.getLogger("sentinel.store")

Listener = Callable[[dict[str, Any]], Any]


class IncidentStore:
    def __init__(self) -> None:
        self.incidents: dict[str, m.Incident] = {}
        self._listeners: dict[str, set[asyncio.Queue]] = {}

    # ---- lifecycle ----------------------------------------------------
    def create(self, title: str, severity: m.Severity, channel: str) -> m.Incident:
        inc = m.Incident(title=title, severity=severity, channel=channel)
        self.incidents[inc.id] = inc
        self._timeline(inc, "incident", f"{severity.value} declared: {title}")
        return inc

    def get(self, incident_id: str) -> m.Incident:
        return self.incidents[incident_id]

    def by_channel(self, channel: str) -> Optional[m.Incident]:
        for inc in self.incidents.values():
            if inc.channel == channel:
                return inc
        return None

    # ---- pub/sub -----------------------------------------------------
    def subscribe(self, incident_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._listeners.setdefault(incident_id, set()).add(q)
        return q

    def unsubscribe(self, incident_id: str, q: asyncio.Queue) -> None:
        self._listeners.get(incident_id, set()).discard(q)

    def broadcast(self, incident_id: str, msg: dict[str, Any]) -> None:
        for q in list(self._listeners.get(incident_id, ())):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                log.warning("dropping ws message; slow consumer")

    def publish_state(self, inc: m.Incident) -> None:
        inc.version += 1
        try:
            _db.mark_dirty(inc.id)
        except Exception:
            pass
        self.broadcast(inc.id, {"type": "state", "incident": inc.model_dump(mode="json")})

    # ---- mutations ---------------------------------------------------
    def _timeline(self, inc: m.Incident, kind: str, text: str, ref: Optional[str] = None) -> m.TimelineEvent:
        ev = m.TimelineEvent(kind=kind, text=text, ref=ref)  # type: ignore[arg-type]
        inc.timeline.append(ev)
        self.broadcast(inc.id, {"type": "event", "event": ev.model_dump(mode="json")})
        return ev

    def add_participant(self, inc: m.Incident, uid: str, name: str, role: m.Role = m.Role.UNKNOWN,
                        focus: str = "") -> m.Participant:
        p = inc.participants.get(uid)
        if p:
            p.online = True
            if name:
                p.name = name
            if role != m.Role.UNKNOWN:
                p.role, p.role_source = role, "declared"
        else:
            p = m.Participant(uid=uid, name=name or uid, role=role, focus=focus)
            inc.participants[uid] = p
            self._timeline(inc, "participant", f"{p.name} joined the room" + (f" as {role.value.replace('_', ' ')}" if role != m.Role.UNKNOWN else ""))
        self.publish_state(inc)
        return p

    def add_transcript(self, inc: m.Incident, uid: str, text: str, final: bool = True,
                       turn_id: Optional[int] = None) -> m.TranscriptLine:
        line = m.TranscriptLine(uid=uid, name=inc.name_of(uid), text=text, final=final, turn_id=turn_id)
        inc.transcript.append(line)
        self.broadcast(inc.id, {"type": "transcript", "line": line.model_dump(mode="json")})
        return line

    def sentinel_said(self, inc: m.Incident, text: str, action: str = "SUMMARIZE") -> None:
        inc.transcript.append(m.TranscriptLine(uid="sentinel", name="Sentinel", text=text))
        self._timeline(inc, "sentinel", f"[{action}] {text}")
        self.broadcast(inc.id, {"type": "sentinel", "text": text, "action": action})
        self.publish_state(inc)

    def set_metrics(self, inc: m.Incident, metrics: dict[str, float], note: Optional[str] = None) -> None:
        inc.metrics = metrics
        if note:
            self._timeline(inc, "metric", note)
        self.broadcast(inc.id, {"type": "metrics", "metrics": metrics})

    # ---- op application (LLM output -> state) --------------------------
    def apply_ops(self, inc: m.Incident, ops: list[dict[str, Any]]) -> list[str]:
        """Apply extractor ops. Returns human-readable change notes."""
        notes: list[str] = []
        for op in ops:
            try:
                note = self._apply(inc, op)
                if note:
                    notes.append(note)
            except Exception as e:  # never let one bad op poison the batch
                log.warning("bad op %s: %s", op, e)
        if notes:
            self.publish_state(inc)
        return notes

    def _find(self, items: list, item_id: str):
        for it in items:
            if it.id == item_id:
                return it
        return None

    def _dupe(self, items: list, attr: str, text: str) -> bool:
        t = text.strip().lower()
        return any(getattr(i, attr).strip().lower() == t for i in items)

    def _apply(self, inc: m.Incident, op: dict[str, Any]) -> Optional[str]:
        kind = op.get("op")
        who = inc.name_of

        if kind == "add_observation":
            if self._dupe(inc.observations, "text", op["text"]):
                return None
            o = m.Observation(text=op["text"], by=op.get("by") or "unknown")
            inc.observations.append(o)
            return None  # observations don't hit the timeline (too noisy)

        if kind == "add_fact":
            if self._dupe(inc.facts, "text", op["text"]):
                return None
            ev = [m.Evidence(**e) for e in op.get("evidence", []) if e.get("source") and e.get("summary")]
            f = m.Fact(text=op["text"], confidence=float(op.get("confidence", 0.9)), evidence=ev)
            inc.facts.append(f)
            self._timeline(inc, "fact", f"Fact: {f.text}", f.id)
            return f"fact: {f.text}"

        if kind == "add_hypothesis":
            if self._dupe(inc.hypotheses, "text", op["text"]):
                return None
            h = m.Hypothesis(text=op["text"], proposed_by=op.get("proposed_by") or "unknown",
                             confidence=float(op.get("confidence", 0.3)))
            inc.hypotheses.append(h)
            self._timeline(inc, "hypothesis", f"Hypothesis ({who(h.proposed_by)}): {h.text}", h.id)
            return f"hypothesis: {h.text}"

        if kind == "update_hypothesis":
            h = self._find(inc.hypotheses, op["id"])
            if not h:
                return None
            ev = op.get("evidence")
            if ev and ev.get("summary"):
                e = m.Evidence(source=ev.get("source", "participant"), summary=ev["summary"],
                               by=ev.get("by"), supports=bool(ev.get("supports", True)))
                (h.supporting if e.supports else h.contradicting).append(e)
            if op.get("status"):
                h.status = m.HypothesisStatus(op["status"])
            if op.get("confidence") is not None:
                h.confidence = float(op["confidence"])
            h.last_verified = m.now()
            label = {"confirmed": "✅ Confirmed", "rejected": "❌ Rejected", "investigating": "🔎 Investigating"}.get(h.status.value, h.status.value)
            self._timeline(inc, "hypothesis", f"{label}: {h.text}", h.id)
            if h.status == m.HypothesisStatus.CONFIRMED and not self._dupe(inc.facts, "text", h.text):
                inc.facts.append(m.Fact(text=h.text, confidence=h.confidence, evidence=list(h.supporting)))
            return f"hypothesis {h.status.value}: {h.text}"

        if kind == "add_action":
            if self._dupe(inc.actions, "text", op["text"]):
                return None
            a = m.Action(text=op["text"], owner=op.get("owner"), created_by=op.get("created_by"),
                         priority=m.Priority(op.get("priority", "normal")))
            if a.owner:
                a.status = m.ActionStatus.IN_PROGRESS
            inc.actions.append(a)
            self._timeline(inc, "action", f"Action → {who(a.owner)}: {a.text}", a.id)
            return f"action ({who(a.owner)}): {a.text}"

        if kind == "update_action":
            a = self._find(inc.actions, op["id"])
            if not a:
                return None
            if op.get("owner"):
                a.owner = op["owner"]
                if a.status == m.ActionStatus.OPEN:
                    a.status = m.ActionStatus.IN_PROGRESS
            if op.get("status"):
                a.status = m.ActionStatus(op["status"])
            if op.get("result"):
                a.result = op["result"]
            a.last_update = m.now()
            self._timeline(inc, "action", f"Action {a.status.value.replace('_', ' ')} ({who(a.owner)}): {a.text}" + (f" — {a.result}" if a.result else ""), a.id)
            return f"action {a.status.value}: {a.text}"

        if kind == "add_decision":
            if self._dupe(inc.decisions, "text", op["text"]):
                return None
            d = m.Decision(seq=len(inc.decisions) + 1, text=op["text"], reason=op.get("reason", ""),
                           participants=op.get("participants", []), approved_by=op.get("approved_by"))
            inc.decisions.append(d)
            self._timeline(inc, "decision", f"Decision #{d.seq}: {d.text}" + (f" (approved by {who(d.approved_by)})" if d.approved_by else ""), d.id)
            return f"decision: {d.text}"

        if kind == "add_conflict":
            if any(c.status == "open" and c.topic.lower() == op["topic"].lower() for c in inc.conflicts):
                return None
            c = m.Conflict(topic=op["topic"], claim_a=op["claim_a"], by_a=op.get("by_a", "?"),
                           claim_b=op["claim_b"], by_b=op.get("by_b", "?"))
            inc.conflicts.append(c)
            self._timeline(inc, "conflict", f"⚠ Conflict on {c.topic}: {who(c.by_a)} says “{c.claim_a}” vs {who(c.by_b)} says “{c.claim_b}”", c.id)
            return f"conflict: {c.topic}"

        if kind == "resolve_conflict":
            c = self._find(inc.conflicts, op["id"])
            if not c:
                return None
            c.status, c.resolution = "resolved", op.get("resolution", "")
            self._timeline(inc, "conflict", f"Conflict resolved on {c.topic}: {c.resolution}", c.id)
            return f"conflict resolved: {c.topic}"

        if kind == "add_unknown":
            if self._dupe(inc.unknowns, "question", op["question"]):
                return None
            u = m.Unknown(question=op["question"], why_it_matters=op.get("why_it_matters", ""))
            inc.unknowns.append(u)
            self._timeline(inc, "unknown", f"Unknown: {u.question}", u.id)
            return f"unknown: {u.question}"

        if kind == "answer_unknown":
            u = self._find(inc.unknowns, op["id"])
            if not u:
                return None
            u.status, u.answer = "answered", op.get("answer", "")
            self._timeline(inc, "unknown", f"Answered: {u.question} → {u.answer}", u.id)
            return f"answered: {u.question}"

        if kind == "add_risk":
            if self._dupe(inc.risks, "text", op["text"]):
                return None
            r = m.Risk(text=op["text"], severity=op.get("severity", "medium"))
            inc.risks.append(r)
            self._timeline(inc, "risk", f"Risk ({r.severity}): {r.text}", r.id)
            return f"risk: {r.text}"

        if kind == "set_role":
            p = inc.participants.get(op["uid"])
            if not p:
                return None
            role = m.Role(op["role"])
            if p.role_source == "corrected":
                return None  # humans win
            if p.role != role:
                p.role, p.role_source = role, "inferred"
                p.focus = op.get("focus", p.focus)
                self._timeline(inc, "participant", f"Role inferred: {p.name} → {role.value.replace('_', ' ')}", p.uid)
                return f"role: {p.name}={role.value}"
            return None

        if kind == "set_status":
            st = m.IncidentStatus(op["status"])
            if inc.status != st:
                inc.status = st
                if st in (m.IncidentStatus.RECOVERED, m.IncidentStatus.RESOLVED):
                    inc.resolved_at = m.now()
                self._timeline(inc, "incident", f"Status → {st.value}")
                return f"status: {st.value}"
            return None

        if kind == "set_impact":
            inc.impact_summary = op["text"]
            return None

        if kind == "propose_tool":
            # handled by the gateway; recorded here so the store stays the source of truth
            return None

        log.debug("unknown op %s", kind)
        return None


store = IncidentStore()
