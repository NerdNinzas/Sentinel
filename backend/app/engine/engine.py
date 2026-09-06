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
from app.tools.adapters import jira, slack
from app.tools import gateway
from app.tools import github as gh

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
        self.wake: dict[str, asyncio.Event] = {}
        self.workers: dict[str, asyncio.Task] = {}
        self.scenarios: dict[str, asyncio.Task] = {}
        self.prev_metrics: dict[str, float] = {}
        self.agora = AgoraConvoAI()
        self._followup: Optional[asyncio.Task] = None
        self._slack_task: Optional[asyncio.Task] = None
        self.slack_incidents: set[str] = set()   # incidents with live Slack participants
        self.claim_checked: set[str] = set()     # "incident:uid:bucket" claims already verified

    # ---- lifecycle ----------------------------------------------------
    async def start(self) -> None:
        monitoring.subscribe(self.on_metrics)
        self._followup = asyncio.create_task(self._followup_loop())
        if get_settings().slack_bot_token:
            self._slack_task = asyncio.create_task(self._slack_loop())
        if get_settings().monitor_url:
            asyncio.create_task(self._live_monitor_loop())
            asyncio.create_task(self._loadgen_loop())

    async def stop(self) -> None:
        for t in list(self.scenarios.values()) + list(self.workers.values()) + [x for x in (self._followup, self._slack_task) if x]:
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
        # ignore duplicates (Agora delivers the same utterance via RTM AND the LLM call,
        # with slightly different punctuation/casing — compare normalized forms)
        import difflib
        import re as _re
        def _norm(t: str) -> str:
            return _re.sub(r"[^a-z0-9 ]+", "", t.lower()).strip()
        # acoustic echo: the mic picks up Sentinel's own TTS — drop only CLOSE matches
        # of a recent, substantial Sentinel line (loose thresholds were eating real speech)
        for l in inc.transcript[-6:]:
            if l.uid == "sentinel" and len(l.text) > 20 and (m.now() - l.at).total_seconds() < 25:
                if difflib.SequenceMatcher(None, _norm(l.text), _norm(text)).ratio() > 0.72:
                    return None
        for l in inc.transcript[-8:]:
            age = (m.now() - l.at).total_seconds()
            sim = difflib.SequenceMatcher(None, _norm(l.text), _norm(text)).ratio()
            # anonymous callback copy vs attributed RTM copy of the SAME utterance
            if age < 15 and sim > 0.55 and ("unknown" in (uid, l.uid)) and uid != l.uid:
                return l
            # true double-delivery: same speaker, near-identical, within seconds
            if age < 8 and l.uid == uid and sim > 0.92:
                return l
        line = store.add_transcript(inc, uid, text, final=final, turn_id=turn_id)
        if final:
            self.pending.setdefault(inc.id, []).append(line)
            if schedule:
                self._schedule(inc)
        return line

    def _schedule(self, inc: m.Incident) -> None:
        """Wake the incident's worker. A worker never cancels in-flight work:
        lines that arrive during an LLM call are simply picked up by the next
        tick (the pending list is the queue)."""
        self.wake.setdefault(inc.id, asyncio.Event()).set()
        w = self.workers.get(inc.id)
        if not w or w.done():
            self.workers[inc.id] = asyncio.create_task(self._worker(inc))

    async def _worker(self, inc: m.Incident) -> None:
        ev = self.wake[inc.id]
        while True:
            await ev.wait()
            await asyncio.sleep(DEBOUNCE_S)   # let a burst of lines coalesce
            ev.clear()
            try:
                speech = await self.tick(inc)
                if speech:
                    await self.say(inc, *speech)
            except Exception as e:
                log.exception("tick failed: %s", e)

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
            rolled = any(p.tool in ("rollback_deployment", "open_revert_pr") and p.approval == m.ApprovalStatus.APPROVED for p in inc.proposals)
            if rolled:
                ops.append({"op": "add_fact", "text": "Recovery followed the approved rollback/revert", "confidence": 0.9,
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
            if llm.available() and lines:      # metrics-only ticks don't need the LLM
                try:
                    result = await llm_extract(inc, lines, events)
                except Exception as e:
                    log.warning("llm extract failed, using rules: %s", e)
                    result = rules.extract(inc, lines)
            else:
                result = rules.extract(inc, lines)
            await self._apply(inc, result.get("ops", []))
            await self._apply(inc, self._state_rules(inc))
            await self._apply(inc, self._repo_evidence_rules(inc))
            if inc.repo or jira.configured:
                import re as _re
                claim_re = _re.compile(r"\b(pushed|committed|merged|deployed|raised (a |the )?pr|opened (a |the )?pr|completed .{0,40}(push|deploy|merge)|i('ve| have)? (completed|finished).{0,50}(push|code|backend|fix|test))", _re.I)
                for line in lines:
                    if line.uid != "sentinel" and claim_re.search(line.text):
                        asyncio.create_task(self.verify_claim(inc, line.uid, line.text))
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
        if inc.id in self.slack_incidents:
            try:
                await slack.post(inc, f"🤖 {text}")
            except Exception as e:
                log.warning("slack echo failed: %s", e)
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

    # ---- live telemetry from the deployed demo service -----------------------
    async def _live_monitor_loop(self) -> None:
        import httpx as _hx
        url = get_settings().monitor_url.rstrip("/")
        async with _hx.AsyncClient(timeout=8) as c:
            while True:
                await asyncio.sleep(5)
                try:
                    if any(not t.done() for t in self.scenarios.values()):
                        continue   # scripted demo drives the metrics; don't stomp it
                    h = (await c.get(f"{url}/health")).json()
                    await monitoring.ingest_live(h)
                    lg = (await c.get(f"{url}/logs", params={"limit": 3})).json().get("logs", [])
                    if lg:
                        for inc in store.incidents.values():
                            if inc.status != m.IncidentStatus.RESOLVED:
                                self.events.setdefault(inc.id, []).extend(
                                    f"service log [{x['level']}] {x['msg']}" for x in lg[-2:])
                except Exception as e:
                    log.debug("live monitor: %s", e)

    async def _loadgen_loop(self) -> None:
        """Keep real traffic flowing at the deployed service so the bug (and the
        recovery) show up in genuine metrics."""
        import httpx as _hx
        url = get_settings().monitor_url.rstrip("/")
        async with _hx.AsyncClient(timeout=10) as c:
            while True:
                live = any(i.status != m.IncidentStatus.RESOLVED for i in store.incidents.values())
                rps = get_settings().loadgen_rps if live else 0.2
                try:
                    await c.post(f"{url}/pay")
                except Exception:
                    pass
                await asyncio.sleep(max(0.2, 1.0 / rps))

    # ---- claim verification: does GitHub agree with what they said? ----------
    CLAIM_RE = None  # set below

    async def _github_token_for(self, uid: str) -> Optional[str]:
        """Best token for verification: the claimant's, else any org member's, else env."""
        from app.core import db
        if db.available():
            u = await db.db().users.find_one({"login": uid, "github_token": {"$nin": [None, ""]}})
            if u:
                return u["github_token"]
            u = await db.db().users.find_one({"github_token": {"$nin": [None, ""]}})
            if u:
                return u["github_token"]
        return get_settings().github_token or None

    async def _github_login_for(self, inc: m.Incident, uid: str) -> Optional[str]:
        from app.core import db
        first = inc.name_of(uid).split()[0].lower()
        if db.available():
            u = await db.db().users.find_one({"login": uid})
            if u and u.get("github_login"):
                return u["github_login"]
            async for u in db.db().users.find({"github_login": {"$nin": [None, ""]}}):
                if (u.get("name") or "").split()[0].lower() == first:
                    return u["github_login"]
        return None

    async def verify_claim(self, inc: m.Incident, uid: str, claim_text: str) -> None:
        """Someone said work is pushed/deployed/done. Check GitHub and Jira for proof."""
        if not inc.repo and not jira.configured:
            return
        key = f"{inc.id}:{uid}:{int(time.time() // 120)}"
        if key in self.claim_checked:
            return
        self.claim_checked.add(key)
        name = inc.name_of(uid)
        # ---- Jira leg: what does the board say about this person's work? ----
        jira_note = ""
        if jira.configured:
            issues = await jira.issues_for(name.split()[0])
            if issues:
                head = "; ".join(f"{i['key']} “{i['summary'][:30]}” · {i['status']}" for i in issues[:3])
                store._timeline(inc, "jira", f"🔎 Checked Jira for {name}: {head}")
                not_done = [i for i in issues if i["status"].lower() not in ("done", "closed", "resolved")]
                if not_done:
                    jira_note = f" On Jira, {not_done[0]['key']} is still {not_done[0]['status']} — should it move?"
                else:
                    jira_note = f" Jira agrees: {issues[0]['key']} is {issues[0]['status']}."
            else:
                store._timeline(inc, "jira", f"🔎 Checked Jira for {name}: no assigned tickets found")
            store.publish_state(inc)
        if not inc.repo:
            if jira_note:
                await self.say(inc, f"{name}, noted.{jira_note}", "SUMMARIZE", "medium")
            return
        gh_login = await self._github_login_for(inc, uid)
        token = await self._github_token_for(uid)
        data = await gh.fetch_changes(inc.repo, inc.started_at, token=token)
        if (data.get("error") or not data.get("commits")) and token:
            data = await gh.fetch_changes(inc.repo, inc.started_at, token=None)  # stale token? public repo works bare
        first = name.split()[0].lower()
        now_ts = m.now()
        matches = []
        for c in data.get("commits", []):
            if not c.get("at"):
                continue
            at = m.datetime.fromisoformat(c["at"].replace("Z", "+00:00"))
            age_min = (now_ts - at).total_seconds() / 60
            author = (c.get("author") or "").lower()
            author_ok = (gh_login and author == gh_login.lower()) or first in author
            if author_ok and abs(age_min) <= get_settings().github_suspect_minutes:
                matches.append((c, age_min))
        if matches:
            c, age = min(matches, key=lambda x: x[1])
            txt = f"Verified: {name}'s update matches GitHub — {inc.repo}@{c['sha']} “{c['message'][:60]}” by {c['author']}, {age:.0f} min ago"
            await self._apply(inc, [{"op": "add_fact", "text": txt, "confidence": 0.95,
                                     "evidence": [{"source": "deployment", "summary": f"{c['url']}"},
                                                  {"source": "participant", "summary": f"{name}: {claim_text[:100]}", "by": uid}]}])
            for a in inc.actions:
                if a.owner == uid and a.status == m.ActionStatus.DONE and not (a.result or "").startswith("✅"):
                    a.result = f"✅ verified · {c['sha']} — {(a.result or claim_text)[:80]}"
            store.publish_state(inc)
            await self.say(inc, f"Verified — I can see {c['author']}'s commit {c['sha']} on {inc.repo}, {age:.0f} minutes ago. {name}'s update checks out.{jira_note}", "SUMMARIZE", "medium")
        else:
            await self._apply(inc, [{"op": "add_risk", "text": f"Unverified claim: {name} reported “{claim_text[:70]}” but no matching commit found on {inc.repo} in the last 90 min", "severity": "medium"}])
            await self.say(inc, f"{name}, I couldn't verify that on GitHub — I don't see a recent commit from you on {inc.repo}. Is the push on another branch, or still local?{jira_note}", "WARN", "medium")

    # ---- Slack channel ingest (read side of the org Slack integration) ------
    async def _slack_loop(self) -> None:
        last_ts = time.time()
        while True:
            await asyncio.sleep(4)
            try:
                live = [i for i in store.incidents.values() if i.status != m.IncidentStatus.RESOLVED]
                if not live:
                    continue
                inc = max(live, key=lambda i: i.started_at)
                msgs = await slack.history(last_ts)
                for msg in msgs:
                    last_ts = max(last_ts, msg["ts"])
                    name = await slack.user_name(msg["user"])
                    uid = "slack-" + name.split()[0].lower()
                    # reuse an existing participant with the same first name (voice+slack same person)
                    for p in inc.participants.values():
                        if p.name.split()[0].lower() == name.split()[0].lower():
                            uid = p.uid
                            break
                    else:
                        store.add_participant(inc, uid, name, focus="via Slack")
                    self.slack_incidents.add(inc.id)
                    line = self.ingest_transcript(inc, uid, msg["text"])
                    if line is not None:
                        store._timeline(inc, "slack", f"💬 Slack #{get_settings().slack_channel.lstrip('#')} · {name}: “{msg['text'][:70]}”")
            except Exception as e:
                log.warning("slack loop: %s", e)

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

    # ---- linked GitHub repo --------------------------------------------------
    async def link_repo(self, inc: m.Incident, repo: str, token: str | None = None) -> None:
        inc.repo = repo
        data = await gh.fetch_changes(repo, inc.started_at, token=token)
        inc.repo_changes = data
        if data.get("error"):
            store._timeline(inc, "tool", f"🔗 Linked {repo} — {data['error']}")
            store.publish_state(inc)
            return
        commits, prs = data["commits"], data["merged_prs"]
        head = commits[0] if commits else None
        note = f"🔗 Linked {repo}@{data['branch']}: {len(commits)} commits, {len(prs)} merged PRs in the last 24h"
        if head and head.get("minutes_before_incident") is not None:
            note += f" — latest {head['sha']} “{head['message'][:50]}” ({head['minutes_before_incident']} min before incident)"
        store._timeline(inc, "tool", note)
        ops: list[dict] = []
        if commits or prs:
            for u in inc.unknowns:
                if u.status == "open" and "changed" in u.question.lower():
                    top = [f"{c['sha']} “{c['message'][:40]}” by {c['author']}" for c in commits[:3]]
                    ops.append({"op": "answer_unknown", "id": u.id, "answer": f"GitHub {repo}: " + "; ".join(top)})
        suspects = [c for c in commits if c.get("suspect")]
        if suspects:
            ops.append({"op": "add_risk", "text": f"{len(suspects)} recent change(s) correlate with the incident ({', '.join(c['sha'] for c in suspects[:3])}) — correlation unverified", "severity": "medium"})
        if ops:
            await self._apply(inc, ops)
        store.publish_state(inc)

    async def link_jira(self, inc: m.Incident) -> None:
        """Show the room what Sentinel sees on the Jira board right now."""
        if not jira.configured:
            return
        issues = await jira.open_issues()
        from app.core.config import get_settings as _gs
        key = _gs().jira_project_key
        if not issues:
            store._timeline(inc, "jira", f"🗂 Jira {key}: no open tickets")
        else:
            head = "; ".join(f"{i['key']} “{i['summary'][:35]}” ({i['assignee'] or 'unassigned'} · {i['status']})" for i in issues[:3])
            store._timeline(inc, "jira", f"🗂 Jira {key}: {len(issues)} open — {head}")
        store.publish_state(inc)

    def _repo_evidence_rules(self, inc: m.Incident) -> list[dict]:
        """Attach the most suspect recent commit as evidence to causal hypotheses."""
        ops: list[dict] = []
        suspects = [c for c in inc.repo_changes.get("commits", []) if c.get("suspect")]
        if not suspects:
            return ops
        c0 = min(suspects, key=lambda c: c.get("minutes_before_incident") or 9e9)
        summary = f"GitHub {inc.repo}@{c0['sha']} “{c0['message'][:60]}” by {c0['author']}, {c0['minutes_before_incident']} min before incident"
        for h in inc.hypotheses:
            if confidence.CAUSAL.search(h.text) and h.status not in (m.HypothesisStatus.REJECTED,):
                if not any(e.source == "deployment" for e in h.supporting):
                    ops.append({"op": "update_hypothesis", "id": h.id,
                                "evidence": {"source": "deployment", "summary": summary, "supports": True}})
        return ops

    # ---- Agora agent --------------------------------------------------------
    def system_prompt(self, inc: m.Incident) -> str:
        from app.llm.prompts import SENTINEL_PERSONA
        return SENTINEL_PERSONA + f"\nIncident {inc.id}: {inc.title} ({inc.severity.value})."

    async def start_agent(self, inc: m.Incident, token: str) -> dict:
        body = self.agora.build_join_body(
            channel=inc.channel, token=token, system_prompt=self.system_prompt(inc),
            greeting=f"Sentinel here. I've joined {inc.title}. I'll track facts, hypotheses, actions and conflicts, and I'll only speak when it helps.",
            name=f"sentinel-{inc.id.lower()}-{int(time.time())}")
        res = None
        for attempt in range(3):   # Agora's managed model service occasionally 500s transiently
            try:
                res = await self.agora.join(body)
                break
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 * (attempt + 1))
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
