"""Turn transcript lines into state operations.

Two implementations with the same signature:
  * llm_extract   — structured JSON from the configured model (preferred)
  * rule_extract  — deterministic patterns; keeps the demo working with no
                    API key and doubles as a safety net when the LLM is slow.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.engine import models as m
from app.llm import client as llm
from app.llm.prompts import EXTRACTION_SYSTEM

log = logging.getLogger("sentinel.extract")

HYPOTHESIS_CUES = ("i think", "i suspect", "probably", "might be", "could be", "my guess",
                   "maybe", "possibly", "looks like it could", "i believe", "seems like")
POSITIVE = ("healthy", "looks fine", "is fine", "normal", "no issues", "looks ok", "looks okay", "fine")
NEGATIVE = ("exhausted", "100%", "overloaded", "saturated", "slow", "failing", "down",
            "maxed", "at capacity", "timing out", "errors", "spiking", "degraded")
TOPICS = {
    "database health": ("database", "db ", "db.", "connection pool", "connections", "postgres", "the db"),
    "deployment": ("deploy", "deployment", "release", "v4.2", "rollout"),
    "authentication": ("auth", "login", "authentication", "token"),
    "region": ("region", "regional", "us-east", "eu-", "ap-"),
    "cache": ("cache", "redis"),
}
ACTION_VERBS = r"(check|look into|look at|investigate|verify|confirm|pull|grab|dig into|review|compare|find out|get)"
DONE_CUES = ("confirmed", "verified", "just checked", "i checked", "is exhausted", "it's exhausted",
             "found it", "i can confirm", "checked it", "it is exhausted")
CRITICAL_TOOLS = {
    "rollback": ("rollback_deployment", lambda t: {"service": "payment-api", "version": _version(t) or "v4.2"}),
    "roll back": ("rollback_deployment", lambda t: {"service": "payment-api", "version": _version(t) or "v4.2"}),
    "restart": ("restart_service", lambda t: {"service": _service(t)}),
    "failover": ("failover_database", lambda t: {"database": "payments-db"}),
    "fail over": ("failover_database", lambda t: {"database": "payments-db"}),
    "scale up": ("scale_service", lambda t: {"service": _service(t), "replicas": 8}),
    "disable the flag": ("disable_feature_flag", lambda t: {"flag": "unknown"}),
}


def _version(t: str) -> str | None:
    mm = re.search(r"\bv?\d+\.\d+(\.\d+)?\b", t)
    return mm.group(0) if mm else None


def _service(t: str) -> str:
    mm = re.search(r"\b([a-z]+-(api|service|worker|gateway))\b", t)
    return mm.group(1) if mm else "payment-api"


def _topic(text: str) -> str | None:
    t = text.lower()
    for topic, keys in TOPICS.items():
        if any(k in t for k in keys):
            return topic
    return None


def _polarity(text: str) -> int:
    t = text.lower()
    neg = any(k in t for k in NEGATIVE)
    pos = any(k in t for k in POSITIVE)
    if neg and not pos:
        return -1
    if pos and not neg:
        return 1
    return 0


def _match_participant(inc: m.Incident, text: str, exclude: str | None = None) -> str | None:
    t = text.lower()
    for uid, p in inc.participants.items():
        if uid == exclude:
            continue
        first = p.name.split()[0].lower()
        if re.search(rf"\b{re.escape(first)}\b", t):
            return uid
    return None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().rstrip(".!?") or text


# --------------------------------------------------------------------------
# Rule-based extractor
# --------------------------------------------------------------------------
class RuleExtractor:
    def __init__(self) -> None:
        # claims[topic] = list of (uid, polarity, text)
        self.claims: dict[str, list[tuple[str, int, str]]] = {}

    def extract(self, inc: m.Incident, lines: list[m.TranscriptLine]) -> dict[str, Any]:
        ops: list[dict[str, Any]] = []
        intervention = {"action": "WAIT", "speech": "", "urgency": "low"}
        for line in lines:
            ops_l, iv = self._line(inc, line)
            ops.extend(ops_l)
            if iv and (intervention["action"] == "WAIT" or iv["urgency"] == "high"):
                intervention = iv
        return {"ops": ops, "intervention": intervention}

    def _line(self, inc: m.Incident, line: m.TranscriptLine):
        ops: list[dict[str, Any]] = []
        iv: dict[str, Any] | None = None
        uid, text = line.uid, line.text
        t = text.lower()
        speaker = inc.name_of(uid)
        p = inc.participants.get(uid)
        role = p.role if p else m.Role.UNKNOWN

        # -- role inference -------------------------------------------------
        if p and p.role == m.Role.UNKNOWN:
            if "customer" in t:
                ops.append({"op": "set_role", "uid": uid, "role": "support", "focus": "Customer impact"})
            elif any(k in t for k in ("node", "cluster", "pod", "infra", "kubernetes", "monitoring shows")):
                ops.append({"op": "set_role", "uid": uid, "role": "sre", "focus": "Infrastructure"})
            elif any(k in t for k in ("connection pool", "the api", "our service", "endpoint")):
                ops.append({"op": "set_role", "uid": uid, "role": "backend", "focus": "Payment API"})
            elif any(k in t for k in ("let's", "everyone", "status update", "approved")):
                ops.append({"op": "set_role", "uid": uid, "role": "incident_commander", "focus": "Coordination"})

        # -- direct question to Sentinel --------------------------------------
        if "sentinel" in t and ("?" in text or any(k in t for k in ("status", "where are we", "summary", "what do we know"))):
            iv = {"action": "CLARIFY", "speech": "__STATUS__", "urgency": "high"}

        # -- customer impact ---------------------------------------------------
        if "customer" in t and any(k in t for k in ("can't", "cannot", "unable", "fail", "complain", "not able", "error")):
            ops.append({"op": "add_observation", "text": _clean(text), "by": uid})
            ops.append({"op": "add_fact", "text": "Customers are unable to complete payments", "confidence": 0.85,
                        "evidence": [{"source": "customer", "summary": f"{speaker}: {_clean(text)}", "by": uid}]})
            ops.append({"op": "set_impact", "text": "Customers unable to complete payments"})

        # -- hypotheses --------------------------------------------------------
        if any(c in t for c in HYPOTHESIS_CUES):
            body = text
            for c in HYPOTHESIS_CUES:
                i = t.find(c)
                if i >= 0:
                    body = text[i + len(c):]
                    break
            body = _clean(body).lstrip(" ,that")
            if body:
                ops.append({"op": "add_hypothesis", "text": body[0].upper() + body[1:], "proposed_by": uid, "confidence": 0.35})

        # -- actions -----------------------------------------------------------
        target = _match_participant(inc, text, exclude=uid)
        if target and re.search(rf"\b(can you|could you|please|go|,)\s*.*{ACTION_VERBS}", t) or (target and re.search(ACTION_VERBS, t) and t.startswith(inc.name_of(target).split()[0].lower())):
            task = re.sub(rf"^.*?{ACTION_VERBS}\s*", "", text, flags=re.I)
            ops.append({"op": "add_action", "text": f"Investigate {_clean(task)}", "owner": target,
                        "priority": "critical" if "database" in t or "db" in t else "high", "created_by": uid})
        elif re.search(rf"\b(someone|somebody|anyone|can we)\b.*{ACTION_VERBS}", t):
            task = re.sub(rf"^.*?{ACTION_VERBS}\s*", "", text, flags=re.I)
            ops.append({"op": "add_action", "text": f"Investigate {_clean(task)}", "owner": None, "priority": "high", "created_by": uid})
            iv = iv or {"action": "ASK", "speech": f"That action has no owner yet: {_clean(task)}. Who is taking it?", "urgency": "medium"}
        elif re.search(rf"\b(i'll|i will|let me|i'm on it|i can)\b.*{ACTION_VERBS}?", t) and not any(c in t for c in HYPOTHESIS_CUES):
            task = re.sub(r"^.*?\b(i'll|i will|let me|i can)\s*", "", text, flags=re.I)
            if len(task) > 6:
                ops.append({"op": "add_action", "text": _clean(task)[0].upper() + _clean(task)[1:], "owner": uid, "priority": "high", "created_by": uid})

        # -- action completion / findings -------------------------------------
        if any(c in t for c in DONE_CUES):
            for a in inc.actions:
                if a.owner == uid and a.status == m.ActionStatus.IN_PROGRESS:
                    ops.append({"op": "update_action", "id": a.id, "status": "done", "result": _clean(text)})
                    break
            topic = _topic(text)
            for h in inc.hypotheses:
                if h.status in (m.HypothesisStatus.UNVERIFIED, m.HypothesisStatus.INVESTIGATING) and _topic(h.text) == topic and topic:
                    has_monitoring = any(e.source == "monitoring" for e in h.supporting)
                    ops.append({"op": "update_hypothesis", "id": h.id,
                                "status": "confirmed" if has_monitoring else "investigating",
                                "confidence": 0.9 if has_monitoring else 0.6,
                                "evidence": {"source": "participant", "summary": f"{speaker}: {_clean(text)}", "by": uid, "supports": True}})
                    if has_monitoring:
                        iv = {"action": "SUMMARIZE", "urgency": "high",
                              "speech": f"Quick update: {h.text.rstrip('.')} is now confirmed by monitoring and {speaker}'s check. Root cause is still open — we don't yet know why it happened."}

        # -- decisions (commander) ---------------------------------------------
        if role == m.Role.INCIDENT_COMMANDER or "approved" in t or "let's freeze" in t or "let's roll" in t:
            if any(k in t for k in ("let's", "we will", "we'll", "approved", "go ahead", "freeze", "decision")) and not any(c in t for c in HYPOTHESIS_CUES):
                if "freeze" in t:
                    ops.append({"op": "add_decision", "text": "Freeze all deployments", "reason": "Stabilise while investigating", "participants": [uid], "approved_by": uid})
                elif "investigate" in t or "focus" in t:
                    ops.append({"op": "add_decision", "text": _clean(re.sub(r"^.*?(let's|we will|we'll)\s*", "", text, flags=re.I)).capitalize(), "reason": "Team agreement", "participants": [uid], "approved_by": uid})

        # -- critical tool proposals (only when a human proposes) --------------
        for cue, (tool, argfn) in CRITICAL_TOOLS.items():
            if cue in t and not any(c in t for c in ("don't", "do not", "not yet")):
                ops.append({"op": "propose_tool", "tool": tool, "args": argfn(text), "reason": f"{speaker} proposed: {_clean(text)}"})
                ic = next((n.name for n in inc.participants.values() if n.role == m.Role.INCIDENT_COMMANDER), "the incident commander")
                iv = {"action": "PROPOSE", "urgency": "high",
                      "speech": f"{tool.replace('_', ' ').capitalize()} is a production-impacting action, so I won't run it myself. I've queued it for approval — {ic}, please approve or reject it on the dashboard."}
                break

        # -- conflict detection --------------------------------------------------
        topic = _topic(text)
        pol = _polarity(text)
        if topic and pol != 0 and not any(c in t for c in HYPOTHESIS_CUES):
            prior = self.claims.setdefault(topic, [])
            for (puid, ppol, ptext) in prior:
                if puid != uid and ppol != pol:
                    ops.append({"op": "add_conflict", "topic": topic, "claim_a": ptext, "by_a": puid, "claim_b": _clean(text), "by_b": uid})
                    iv = {"action": "WARN", "urgency": "high",
                          "speech": f"I want to flag conflicting information about {topic}. {inc.name_of(puid)} reported “{ptext}”, but {speaker} reports “{_clean(text)}”. Can someone verify the current state before we treat this as settled?"}
                    break
            prior.append((uid, pol, _clean(text)))
            if pol == 1:
                ops.append({"op": "add_observation", "text": _clean(text), "by": uid})

        return ops, iv


# --------------------------------------------------------------------------
# LLM extractor
# --------------------------------------------------------------------------
def _digest(inc: m.Incident) -> dict[str, Any]:
    return {
        "incident": {"id": inc.id, "title": inc.title, "severity": inc.severity.value, "status": inc.status.value,
                     "impact": inc.impact_summary, "metrics": inc.metrics},
        "participants": [{"uid": p.uid, "name": p.name, "role": p.role.value} for p in inc.participants.values()],
        "facts": [{"id": f.id, "text": f.text} for f in inc.facts],
        "hypotheses": [{"id": h.id, "text": h.text, "status": h.status.value, "by": h.proposed_by,
                        "supporting": [e.summary for e in h.supporting], "contradicting": [e.summary for e in h.contradicting]} for h in inc.hypotheses],
        "actions": [{"id": a.id, "text": a.text, "owner": a.owner, "status": a.status.value} for a in inc.actions],
        "decisions": [d.text for d in inc.decisions],
        "conflicts": [{"id": c.id, "topic": c.topic, "status": c.status} for c in inc.conflicts],
        "unknowns": [{"id": u.id, "question": u.question, "status": u.status} for u in inc.unknowns],
        "risks": [r.text for r in inc.risks],
        "pending_approvals": [{"tool": p.tool, "args": p.args} for p in inc.proposals if p.approval == m.ApprovalStatus.PENDING],
    }


async def llm_extract(inc: m.Incident, lines: list[m.TranscriptLine], events: list[str]) -> dict[str, Any]:
    payload = {
        "state": _digest(inc),
        "new_transcript": [{"uid": l.uid, "name": l.name, "text": l.text, "at": l.at.isoformat()} for l in lines],
        "new_monitoring_events": events,
    }
    out = await llm.complete_json(EXTRACTION_SYSTEM, json.dumps(payload, ensure_ascii=False))
    out.setdefault("ops", [])
    out.setdefault("intervention", {"action": "WAIT", "speech": "", "urgency": "low"})
    return out


rules = RuleExtractor()
