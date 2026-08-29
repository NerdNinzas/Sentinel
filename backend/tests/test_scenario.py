import asyncio
import pytest

from app.engine import models as m
from app.engine.engine import engine
from app.engine.store import store
from app.engine import report
from app.mock.monitoring import monitoring


@pytest.mark.asyncio
async def test_end_to_end_scenario():
    await engine.start()
    try:
        inc = store.create("Payment API Outage", m.Severity.SEV1, "test-channel")
        await monitoring.set_phase("baseline")
        await engine._scenario(inc, speed=200.0, auto_approve=True)
        # give the async recovery a moment
        for _ in range(50):
            if inc.status == m.IncidentStatus.RESOLVED and any("recovered" in f.text for f in inc.facts):
                break
            await asyncio.sleep(0.05)
    finally:
        await engine.stop()

    names = {p.name for p in inc.participants.values()}
    assert {"Arjun", "Rahul", "Ananya", "Priya"} <= names
    # role inference: Priya talked about customers -> support
    assert inc.participants["priya"].role == m.Role.SUPPORT

    # facts vs hypotheses
    assert any("payment success rate dropped" in f.text.lower() for f in inc.facts)
    assert any("connection utilization" in f.text.lower() for f in inc.facts)
    assert any("unable to complete payments" in f.text.lower() for f in inc.facts)
    db_h = [h for h in inc.hypotheses if "database" in h.text.lower() or "overloaded" in h.text.lower()]
    assert db_h and db_h[0].status == m.HypothesisStatus.CONFIRMED, [ (h.text, h.status) for h in inc.hypotheses ]
    assert any(e.source == "monitoring" for e in db_h[0].supporting)
    dep_h = [h for h in inc.hypotheses if "v4.2" in h.text.lower() or "deploy" in h.text.lower()]
    assert dep_h and dep_h[0].status != m.HypothesisStatus.CONFIRMED  # correlation only

    # conflict on database health detected and later resolved
    conf = [c for c in inc.conflicts if "database" in c.topic]
    assert conf and conf[0].status == "resolved"

    # actions with owners
    owners = {(a.text.lower()[:20], a.owner) for a in inc.actions}
    assert any(o == "rahul" for _, o in owners)
    assert any(o == "ananya" for _, o in owners)
    assert any(a.owner == "rahul" and a.status == m.ActionStatus.DONE for a in inc.actions)

    # decisions
    assert any("freeze" in d.text.lower() for d in inc.decisions)

    # human-in-the-loop rollback
    rb = [p for p in inc.proposals if p.tool == "rollback_deployment"]
    assert rb and rb[0].risk == "critical" and rb[0].approval == m.ApprovalStatus.APPROVED and rb[0].approved_by == "arjun"
    assert rb[0].result and "rolled back" in rb[0].result["summary"]
    # safe tools auto-executed
    assert any(p.tool == "post_slack_update" and p.approval == m.ApprovalStatus.APPROVED for p in inc.proposals)
    assert any(p.tool == "create_jira_ticket" and p.result for p in inc.proposals)

    # unknowns & risks
    assert any(u.status == "answered" and "authentication" in u.question.lower() for u in inc.unknowns)
    assert any(r.text.lower().startswith("root cause") for r in inc.risks)

    # recovery + confidence
    assert inc.status == m.IncidentStatus.RESOLVED
    assert inc.confidence.customer_impact > 0.9 and inc.confidence.root_cause < 0.6
    said = [l.text for l in inc.transcript if l.uid == "sentinel"]
    assert any("conflicting" in s.lower() for s in said)
    assert any("approval" in s.lower() for s in said)
    assert any("root cause remains unconfirmed" in s.lower() for s in said)

    md = await report.generate(inc)
    assert "Root cause **not conclusively established**" in md


def test_critical_tool_cannot_auto_execute():
    from app.tools import gateway
    inc = store.create("x", m.Severity.SEV2, "c2")
    prop = m.ToolProposal(tool="rollback_deployment", args={}, risk="critical")
    inc.proposals.append(prop)
    asyncio.run(gateway.execute(inc, prop, approved_by="policy:auto"))
    assert prop.approval == m.ApprovalStatus.REJECTED and "policy violation" in (prop.error or "")
