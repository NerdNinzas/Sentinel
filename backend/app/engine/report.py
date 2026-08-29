"""Final incident report + status snapshot text."""
from __future__ import annotations

import json
from app.engine import models as m
from app.engine.confidence import spoken_summary
from app.llm import client as llm
from app.llm.prompts import REPORT_SYSTEM


def status_speech(inc: m.Incident) -> str:
    facts = [f.text for f in inc.facts][-3:]
    hyps = [f"{h.text} ({h.status.value})" for h in inc.hypotheses if h.status != m.HypothesisStatus.REJECTED][:2]
    open_actions = [f"{inc.name_of(a.owner)} on {a.text}" for a in inc.actions if a.status != m.ActionStatus.DONE][:2]
    conflicts = [c.topic for c in inc.conflicts if c.status == "open"]
    unknowns = [u.question for u in inc.unknowns if u.status == "open"][:2]
    parts = []
    parts.append(f"Status: {inc.status.value}. " + (f"Known: {'; '.join(facts)}." if facts else "No confirmed facts yet."))
    if hyps:
        parts.append(f"Working theories: {'; '.join(hyps)}.")
    if conflicts:
        parts.append(f"Unresolved conflict on {', '.join(conflicts)}.")
    if open_actions:
        parts.append(f"In flight: {'; '.join(open_actions)}.")
    if unknowns:
        parts.append(f"Still unknown: {' '.join(unknowns)}")
    parts.append(spoken_summary(inc))
    return " ".join(parts)


def _md(inc: m.Incident) -> str:
    n = inc.name_of
    dur = ((inc.resolved_at or m.now()) - inc.started_at).total_seconds() / 60
    L = [f"# {inc.id} — {inc.title}", "",
         f"**Severity:** {inc.severity.value}  **Status:** {inc.status.value}  **Duration:** {dur:.0f} min", "",
         "## Impact", inc.impact_summary or "_not recorded_", ""]
    if inc.metrics:
        L += ["| Metric | Latest |", "|---|---|"] + [f"| {k} | {v:.1f} |" for k, v in inc.metrics.items()] + [""]
    L += ["## Confirmed Findings"] + [f"- {f.text}" + (f" — evidence: {'; '.join(e.summary for e in f.evidence)}" if f.evidence else "") for f in inc.facts] + [""]
    L += ["## Hypotheses"] + [f"- **{h.status.value}** ({h.confidence:.0%}) {h.text} — proposed by {n(h.proposed_by)}" for h in inc.hypotheses] + [""]
    L += ["## Decision Ledger"] + [f"{d.seq}. {d.text}" + (f" — {d.reason}" if d.reason else "") + (f" _(approved by {n(d.approved_by)})_" if d.approved_by else "") for d in inc.decisions] + [""]
    L += ["## Actions", "| Owner | Action | Status | Result |", "|---|---|---|---|"] + [f"| {n(a.owner)} | {a.text} | {a.status.value} | {a.result or ''} |" for a in inc.actions] + [""]
    L += ["## Tool Executions"] + [f"- {p.tool} {p.args} — {p.approval.value} by {n(p.approved_by) if p.approved_by and not p.approved_by.startswith('policy') else p.approved_by} → {(p.result or {}).get('summary', p.error or 'pending')}" for p in inc.proposals] + [""]
    L += ["## Unresolved Risks"] + [f"- ⚠ {r.text}" for r in inc.risks if r.status == "open"] + [""]
    L += ["## Open Questions"] + [f"- ? {u.question}" for u in inc.unknowns if u.status == "open"] + [""]
    L += ["## Conflicts"] + [f"- {c.topic}: {n(c.by_a)} “{c.claim_a}” vs {n(c.by_b)} “{c.claim_b}” — {c.status}" + (f" ({c.resolution})" if c.resolution else "") for c in inc.conflicts] + [""]
    rc = inc.confidence.root_cause
    L += ["## Root Cause", ("Root cause **not conclusively established** (confidence %.0f%%). " % (rc * 100)) if rc < 0.8 else f"Root cause confidence {rc:.0%}.", "",
          "## Confidence"] + [f"- {k.replace('_', ' ')}: {v:.0%}" for k, v in inc.confidence.model_dump().items()] + [""]
    L += ["## Timeline"] + [f"- {e.at.strftime('%H:%M:%S')} {e.text}" for e in inc.timeline]
    return "\n".join(L)


async def generate(inc: m.Incident) -> str:
    deterministic = _md(inc)
    if not llm.available():
        return deterministic
    try:
        text = await llm.complete_text(REPORT_SYSTEM, json.dumps(inc.model_dump(mode="json"), default=str)[:60000])
        return text + "\n\n---\n\n<details><summary>Raw state report</summary>\n\n" + deterministic + "\n</details>"
    except Exception:
        return deterministic
