"""Sentinel engine: the loop that turns room activity into incident state and
decides when (and how) to speak."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from app.core.agora import AgoraConvoAI
from app.core.config import get_settings
from app.engine import models as m
from app.engine import confidence, report
from app.engine.extractor import llm_extract, rules
from app.engine.store import store
from app.llm import client as llm
from app.mock import scenario
from app.mock.monitoring import monitoring
from app.tools import gateway

log = logging.getLogger("sentinel.engine")

DEBOUNCE_S = 0.8
MIN_GAP_S = 8.0            # between non-urgent utterances
ACTION_STALE_S = 90.0      # chase an in-progress action after this
UNOWNED_STALE_S = 30.0
APPROVAL_REMIND_S = 45.0


class Engine:
    def __init__(self) -> None:
        self.pending: dict[str, list[m.TranscriptLine]] = {}
        self.events: dict[str, list[str]] = {}
        self.locks: dict[str, asyncio.Lock] = {}
        self.last_spoke: dict[str, float] = {}
        self.chased: set[str] = set()
        self.debounce: dict[str, asyncio.Task] = {}
        self.scenarios: dict[str, asyncio.Task] = {}
        self.prev_metrics: dict[str, float] = {}
        self.agora = AgoraConvoAI()
        self._followup: Optional[asyncio.Task] = None

    # ---- lifecycle ----------------------------------------------------
    async def start(self) -> None:
        monitoring.subscribe(self.on_metrics)
        self._followup = asyncio.create_task(self._followup_loop())

    async def stop(self) -> None:
        for t in list(self.scenarios.values()) + ([self._followup] if self._followup else []):
            t.cancel()

    def _lock(self, inc_id: str) -> asyncio.Lock:
        return self.locks.setdefault(inc_id, asyncio.Lock())

    # ---- inputs ------------------------------------------------------
    def ingest_transcript(self, inc: m.Incident, uid: str, text: str, final: bool = True,
                          turn_id: Optional[int] = None, schedule: bool = True) -> Optional[m.TranscriptLine]:
        text = text.strip()
        if not text:
            return None
        if uid not in inc.participants and uid != "sentinel":
            store.add_participant(inc, uid, uid.title())
        # ignore duplicates (Agora may deliver the same final line via RTM and the LLM call)
        for l in inc.transcript[-8:]:
            if l.uid == uid and l.text.strip().lower() == text.lower() and (m.now() - l.at).total_seconds() < 20:
                return l
        line = store.add_transcript(inc, uid, text, final=final, turn_id=turn_id)
        if final:
            self.pending.setdefault(inc.id, []).append(line)
            if schedule:
                self._schedule(inc)
        return line

    def _schedule(self, inc: m.Incident) -> None:
        t = self.debounce.get(inc.id)
        if t and not t.done():
            t.cancel()

        async def later():
            await asyncio.sleep(DEBOUNCE_S)
            speech = await self.tick(inc)
            if speech:
                await self.say(inc, *speech)
        self.debounce[inc.id] = asyncio.create_task(later())

    async def on_metrics(self, metrics: dict[str, float]) -> None:
        prev, self.prev_metrics = self.prev_metrics, dict(metrics)
        for inc in list(store.incidents.values()):
            if inc.status == m.IncidentStatus.RESOLVED:
                continue
            ops, notes = self._metric_rules(inc, prev, metrics)
            store.set_metrics(inc, metrics)
            if ops:
                await self._apply(inc, ops)
            if notes:
                self.events.setdefault(inc.id, []).extend(notes)
            speech = await self._post_metrics_speech(inc, prev, metrics)
            if speech:
                await self.say(inc, *speech)
            inc.confidence = confidence.compute(inc)
            store.publish_state(inc)

    # ---- deterministic rules (never delegated to the LLM) ----------------
    def _has_fact(self, inc: m.Incident, *keys: str) -> bool:
        return any(all(k in f.text.lower() for k in keys) for f in inc.facts)

    def _metric_rules(self, inc: m.Incident, prev: dict, cur: dict) -> tuple[list[dict], list[str]]:
        ops: list[dict[str, Any]] = []
        notes: list[str] = []
        psr, db = cur.get("payment_success_rate", 100), cur.get("db_connection_utilization", 0)
        if psr < 50 and not self._has_fact(inc, "payment success rate", "dropped"):
            txt = f"Payment success rate dropped to {psr:.0f}% (error rate {cur.get('payment_error_rate', 0):.0f}%)"
            ops.append({"op": "add_fact", "text": txt, "confidence": 0.99, "evidence": [{"source": "monitoring", "summary": txt}]})
            notes.append(txt)
            ops.append({"op": "add_unknown", "question": "Is the problem regional or global?", "why_it_matters": "Determines blast radius and whether traffic shifting is an option"})
            ops.append({"op": "add_unknown", "question": "Is authentication affected?", "why_it_matters": "Separates a payment-only failure from a platform-wide one"})
        if db >= 95 and not self._has_fact(inc, "connection utilization"):
            txt = f"DB connection utilization at {db:.0f}%, pool wait {cur.get('db_pool_wait_ms', 0) / 1000:.1f}s"
            ops.append({"op": "add_fact", "text": txt, "confidence": 0.97, "evidence": [{"source": "monitoring", "summary": txt}]})
            notes.append(txt)
            for h in inc.hypotheses:
                if h.status in (m.HypothesisStatus.UNVERIFIED, m.HypothesisStatus.INVESTIGATING) and any(k in h.text.lower() for k in ("database", "db", "pool", "connection")):
                    ops.append({"op": "update_hypothesis", "id": h.id, "status": "investigating", "confidence": 0.7,
                                "evidence": {"source": "monitoring", "summary": txt, "supports": True}})
        auth = cur.get("auth_success_rate")
        if auth and auth > 99:
            for u in inc.unknowns:
                if u.status == "open" and "authentication" in u.question.lower():
                    ops.append({"op": "answer_unknown", "id": u.id, "answer": f"Auth success rate {auth:.1f}% — unaffected (monitoring)"})
        if (psr > 95 and prev.get("payment_success_rate", 100) < 95 and self._has_fact(inc, "payment success rate", "dropped")
                and inc.status not in (m.IncidentStatus.RECOVERED, m.IncidentStatus.RESOLVED)):
            txt = f"Payment success rate recovered to {psr:.1f}%"
            ops.append({"op": "add_fact", "text": txt, "confidence": 0.98, "evidence": [{"source": "monitoring", "summary": txt}]})
            notes.append(txt)
            ops.append({"op": "set_status", "status": "recovered"})
            rolled = any(p.tool == "rollback_deployment" and p.approval == m.ApprovalStatus.APPROVED for p in inc.proposals)
            if rolled:
                ops.append({"op": "add_fact", "text": "Recovery followed the rollback of payment-api v4.2", "confidence": 0.9,
                            "evidence": [{"source": "tool", "summary": "rollback executed then success rate recovered"}]})
                for h in inc.hypotheses:
                    if confidence.CAUSAL.search(h.text) and h.status != m.HypothesisStatus.CONFIRMED:
                        ops.append({"op": "update_hypothesis", "id": h.id, "status": "investigating", "confidence": 0.6,
                                    "evidence": {"source": "tool", "summary": "recovery followed rollback (correlation, not proof)", "supports": True}})
            ops.append({"op": "add_risk", "text": "Root cause not conclusively established", "severity": "high"})
            ops.append({"op": "add_risk", "text": "Deployment v4.2 correlation requires validation before re-deploy", "severity": "medium"})
            ops.append({"op": "add_risk", "text": "Database connection pool configuration needs review", "severity": "medium"})
            ops.append({"op": "propose_tool", "tool": "post_slack_update", "args": {"text": f"{inc.title}: payment success recovered to {psr:.0f}% after rollback. Root cause still under investigation."}, "reason": "status change"})
            ops.append({"op": "propose_tool", "tool": "create_jira_ticket", "args": {"summary": "Review payment-api DB connection pool configuration", "assignee": "rahul"}, "reason": "follow-up from recovery"})
        return ops, notes

    async def _post_metrics_speech(self, inc: m.Incident, prev: dict, cur: dict) -> Optional[tuple[str, str, str]]:
        psr = cur.get("payment_success_rate", 100)
        if psr > 95 and prev.get("payment_success_rate", 100) < 95 and inc.status == m.IncidentStatus.RECOVERED:
            rc = inc.confidence.root_cause
            tail = " However, root cause remains unconfirmed — the deployment link is a correlation, not a proven cause." if rc < 0.8 else ""
            return (f"Payment success has recovered to {psr:.0f}%. The incident appears resolved.{tail}", "SUMMARIZE", "high")
        if cur.get("db_connection_utilization", 0) >= 95 and prev.get("db_connection_utilization", 0) < 95:
            open_conf = [c for c in inc.conflicts if c.status == "open" and "database" in c.topic]
            if open_conf:
                return ("Monitoring now shows database connections at 100 percent, which contradicts the healthy report. Can someone verify the current state before we treat the database as the cause?", "ASK", "high")
            return ("Monitoring shows database connection utilization at 100 percent. That supports the pool-exhaustion theory but doesn't confirm it yet.", "SUMMARIZE", "medium")
        return None

    def _state_rules(self, inc: m.Incident) -> list[dict]:
        """Heuristics that run after every extraction pass."""
        ops: list[dict[str, Any]] = []
        for h in inc.hypotheses:
            if confidence.CAUSAL.search(h.text) and h.status != m.HypothesisStatus.CONFIRMED:
                q = f"Did {h.text.rstrip('.').lower()}? — needs validation"
                if not any(u.question.lower().startswith("did") and "deploy" in u.question.lower() for u in inc.unknowns):
                    ops.append({"op": "add_unknown", "question": "Did deployment v4.2 cause the issue?", "why_it_matters": "Determines whether rollback is a fix or a coincidence"})
        for p in inc.proposals:
            if p.risk == "critical" and p.approval == m.ApprovalStatus.PENDING:
                if not any("safe" in u.question.lower() for u in inc.unknowns):
                    ops.append({"op": "add_unknown", "question": f"Is {p.tool.replace('_', ' ')} safe right now?", "why_it_matters": "Production-impacting action pending approval"})
                    ops.append({"op": "add_risk", "text": f"{p.tool.replace('_', ' ').capitalize()} may not address root cause if the trigger is elsewhere", "severity": "medium"})
            if p.risk == "critical" and p.approval == m.ApprovalStatus.APPROVED:
                for u in inc.unknowns:
                    if u.status == "open" and "safe" in u.question.lower():
                        ops.append({"op": "answer_unknown", "id": u.id, "answer": f"Approved by {inc.name_of(p.approved_by)}"})
        for c in inc.conflicts:
            if c.status == "open" and "database" in c.topic:
                if any(h.status == m.HypothesisStatus.CONFIRMED and any(k in h.text.lower() for k in ("pool", "database", "db")) for h in inc.hypotheses):
                    ops.append({"op": "resolve_conflict", "id": c.id, "resolution": "Node-level health was fine; connection pool was exhausted. Both reports were partially right."})
        for h in inc.hypotheses:
            if h.status == m.HypothesisStatus.CONFIRMED and any(k in h.text.lower() for k in ("pool", "database")):
                if not any(p.tool == "post_slack_update" and "Confirmed:" in str(p.args) for p in inc.proposals):
                    ops.append({"op": "propose_tool", "tool": "post_slack_update", "args": {"text": f"Confirmed: {h.text}. Investigating trigger. Status: {inc.status.value}."}, "reason": "confirmed finding"})
        return ops

    # ---- core tick -------------------------------------------------------
    async def _apply(self, inc: m.Incident, ops: list[dict]) -> list[str]:
        tool_ops = [o for o in ops if o.get("op") == "propose_tool"]
        notes = store.apply_ops(inc, [o for o in ops if o.get("op") != "propose_tool"])
        for o in tool_ops:
            await gateway.propose(inc, o.get("tool", ""), o.get("args") or {}, o.get("reason", ""))
        return notes

    async def tick(self, inc: m.Incident) -> Optional[tuple[str, str, str]]:
        async with self._lock(inc.id):
            lines = self.pending.pop(inc.id, [])
            events = self.events.pop(inc.id, [])
            if not lines and not events:
                return None
            result: dict[str, Any]
            if llm.available():
                try:
                    result = await llm_extract(inc, lines, events)
                except Exception as e:
                    log.warning("llm extract failed, using rules: %s", e)
                    result = rules.extract(inc, lines)
            else:
                result = rules.extract(inc, lines)
            await self._apply(inc, result.get("ops", []))
            await self._apply(inc, self._state_rules(inc))
            inc.confidence = confidence.compute(inc)
            store.publish_state(inc)

            iv = result.get("intervention") or {}
            action, speech, urgency = iv.get("action", "WAIT"), (iv.get("speech") or "").strip(), iv.get("urgency", "low")
            if speech == "__STATUS__":
                speech = report.status_speech(inc)
            if action == "WAIT" or not speech:
                return None
            gap = time.time() - self.last_spoke.get(inc.id, 0)
            if urgency != "high" and gap < MIN_GAP_S:
                return None
            return speech, action, urgency

    async def say(self, inc: m.Incident, text: str, action: str = "SUMMARIZE", urgency: str = "medium") -> None:
        self.last_spoke[inc.id] = time.time()
        store.sentinel_said(inc, text, action)
        if inc.agent_id and self.agora.configured:
            try:
                await self.agora.speak(inc.agent_id, text, priority="INTERRUPT" if urgency == "high" else "APPEND")
            except Exception as e:
                log.warning("speak failed: %s", e)

    # ---- follow-ups ------------------------------------------------------
    async def _followup_loop(self) -> None:
        while True:
            await asyncio.sleep(10)
            try:
                for inc in list(store.incidents.values()):
                    if inc.status in (m.IncidentStatus.RESOLVED,):
                        continue
                    speech = self._followup_for(inc)
                    if speech:
                        await self.say(inc, speech, "ASK", "medium")
            except Exception as e:  # keep the loop alive
                log.exception("followup loop: %s", e)

    def _followup_for(self, inc: m.Incident) -> Optional[str]:
        now = m.now()
        for a in inc.actions:
            age = (now - a.last_update).total_seconds()
            key = f"{a.id}:{int(age // ACTION_STALE_S)}"
            if a.status == m.ActionStatus.IN_PROGRESS and age > ACTION_STALE_S and key not in self.chased:
                self.chased.add(key)
                return f"{inc.name_of(a.owner)}, do we have an update on: {a.text}?"
            if a.status == m.ActionStatus.OPEN and a.owner is None and age > UNOWNED_STALE_S and a.id not in self.chased:
                self.chased.add(a.id)
                return f"Nobody owns this yet: {a.text}. Who can take it?"
        for p in inc.proposals:
            age = (now - p.at).total_seconds()
            if p.approval == m.ApprovalStatus.PENDING and age > APPROVAL_REMIND_S and f"ap:{p.id}" not in self.chased:
                self.chased.add(f"ap:{p.id}")
                ic = next((n.name for n in inc.participants.values() if n.role == m.Role.INCIDENT_COMMANDER), "Commander")
                return f"{ic}, {p.tool.replace('_', ' ')} is still waiting for your approval."
        return None

    # ---- Agora agent --------------------------------------------------------
    def system_prompt(self, inc: m.Incident) -> str:
        from app.llm.prompts import SENTINEL_PERSONA
        return SENTINEL_PERSONA + f"\nIncident {inc.id}: {inc.title} ({inc.severity.value})."

    async def start_agent(self, inc: m.Incident, token: str) -> dict:
        body = self.agora.build_join_body(
            channel=inc.channel, token=token, system_prompt=self.system_prompt(inc),
            greeting=f"Sentinel here. I've joined {inc.title}. I'll track facts, hypotheses, actions and conflicts, and I'll only speak when it helps.",
            name=f"sentinel-{inc.id.lower()}")
        res = await self.agora.join(body)
        inc.agent_id = res.get("agent_id")
        store._timeline(inc, "sentinel", "Sentinel joined the Agora voice room")
        store.publish_state(inc)
        return res

    async def stop_agent(self, inc: m.Incident) -> None:
        if inc.agent_id:
            try:
                await self.agora.leave(inc.agent_id)
            finally:
                inc.agent_id = None
                store.publish_state(inc)

    # ---- demo scenario -------------------------------------------------------
    def run_scenario(self, inc: m.Incident, speed: float = 1.0, auto_approve: bool = False) -> None:
        if (t := self.scenarios.get(inc.id)) and not t.done():
            return
        self.scenarios[inc.id] = asyncio.create_task(self._scenario(inc, speed, auto_approve))

    def stop_scenario(self, inc: m.Incident) -> None:
        if (t := self.scenarios.get(inc.id)):
            t.cancel()

    async def _scenario(self, inc: m.Incident, speed: float, auto_approve: bool) -> None:
        monitoring.speed = speed
        for p in scenario.PARTICIPANTS:
            store.add_participant(inc, p["uid"], p["name"], m.Role(p["role"]), p["focus"])
        await self.say(inc, "Sentinel here. I've joined the room and I'm tracking facts, hypotheses, actions and conflicts. I'll only speak when it helps.", "SUMMARIZE", "low")
        for delay, kind, payload in scenario.STEPS:
            await asyncio.sleep(delay / speed)
            if kind == "say":
                self.ingest_transcript(inc, payload["uid"], payload["text"], schedule=False)
                speech = await self.tick(inc)
                if speech:
                    await self.say(inc, *speech)
            elif kind == "metrics":
                store._timeline(inc, "metric", payload["note"])
                if payload["phase"] != "recovered":
                    await monitoring.set_phase(payload["phase"])
                elif any(p.tool == "rollback_deployment" and p.approval == m.ApprovalStatus.APPROVED for p in inc.proposals):
                    # the deploy adapter drives recovery after a real rollback; wait for it
                    for _ in range(int(60 * speed)):
                        if monitoring.phase == "recovered":
                            break
                        await asyncio.sleep(0.25 / speed)
                else:
                    await monitoring.recover_over(seconds=6)
            elif kind == "await_approval":
                prop = next((p for p in inc.proposals if p.tool == payload["tool"]), None)
                if prop and auto_approve:
                    await gateway.decide(inc, prop.id, True, "arjun")
                deadline = time.time() + 600
                while prop and prop.approval == m.ApprovalStatus.PENDING and time.time() < deadline:
                    await asyncio.sleep(0.5)
                if prop and prop.approval == m.ApprovalStatus.REJECTED:
                    await self.say(inc, "Rollback was rejected. We stay in mitigation; what's the alternative?", "ASK", "high")
                    return
                if prop and prop.approval == m.ApprovalStatus.APPROVED:
                    # Deploy adapter drives recovery; wait for it before the scripted recovery note
                    await asyncio.sleep(1)
        await self._apply(inc, [{"op": "set_status", "status": "resolved"}])
        store._timeline(inc, "incident", "Incident marked resolved — final report available")
        store.publish_state(inc)


engine = Engine()
