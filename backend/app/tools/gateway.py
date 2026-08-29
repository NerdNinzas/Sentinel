"""AI Tool Gateway.

LLM -> ToolProposal -> policy check -> (human approval if critical) ->
adapter execution -> result -> incident timeline. The LLM never touches an
external API directly.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from app.engine import models as m
from app.engine.store import store
from app.tools import adapters

log = logging.getLogger("sentinel.gateway")

ToolFn = Callable[[m.Incident, dict[str, Any]], Awaitable[dict[str, Any]]]


class ToolSpec:
    def __init__(self, name: str, risk: str, description: str, fn: ToolFn):
        self.name, self.risk, self.description, self.fn = name, risk, description, fn


REGISTRY: dict[str, ToolSpec] = {}


def register(name: str, risk: str, description: str):
    def deco(fn: ToolFn):
        REGISTRY[name] = ToolSpec(name, risk, description, fn)
        return fn
    return deco


# ---- safe tools (auto-execute) ----------------------------------------------
@register("post_slack_update", "safe", "Post a status update to the incident Slack channel")
async def _slack(inc: m.Incident, args: dict) -> dict:
    return await adapters.slack.post(inc, args.get("text", ""))


@register("create_jira_ticket", "safe", "Create a Jira task for an investigation / follow-up")
async def _jira(inc: m.Incident, args: dict) -> dict:
    return await adapters.jira.create(inc, args.get("summary", ""), args.get("assignee"), args.get("description", ""))


@register("query_monitoring", "safe", "Read a metric from monitoring")
async def _mon(inc: m.Incident, args: dict) -> dict:
    return adapters.monitoring.query(args.get("metric"))


@register("recent_deployments", "safe", "List recent deployments for a service")
async def _deploys(inc: m.Incident, args: dict) -> dict:
    return {"deployments": adapters.monitoring.recent_deployments(args.get("service"))}


@register("page_oncall", "safe", "Page an on-call responder via PagerDuty")
async def _page(inc: m.Incident, args: dict) -> dict:
    return await adapters.pagerduty.page(inc, args.get("team", "sre"), args.get("reason", ""))


# ---- critical tools (human approval required) -------------------------------
@register("rollback_deployment", "critical", "Roll back a service to the previous version")
async def _rollback(inc: m.Incident, args: dict) -> dict:
    return await adapters.deploy.rollback(inc, args.get("service", "payment-api"), args.get("version"))


@register("restart_service", "critical", "Restart a production service")
async def _restart(inc: m.Incident, args: dict) -> dict:
    return await adapters.deploy.restart(inc, args.get("service", ""))


@register("failover_database", "critical", "Fail over the database to a replica")
async def _failover(inc: m.Incident, args: dict) -> dict:
    return await adapters.deploy.failover(inc, args.get("database", "payments-db"))


@register("scale_service", "critical", "Change replica count of a production service")
async def _scale(inc: m.Incident, args: dict) -> dict:
    return await adapters.deploy.scale(inc, args.get("service", ""), int(args.get("replicas", 0)))


@register("disable_feature_flag", "critical", "Disable a production feature flag")
async def _flag(inc: m.Incident, args: dict) -> dict:
    return await adapters.deploy.disable_flag(inc, args.get("flag", ""))


# ---- gateway ---------------------------------------------------------------
async def propose(inc: m.Incident, tool: str, args: dict, reason: str, proposed_by: str = "sentinel") -> Optional[m.ToolProposal]:
    spec = REGISTRY.get(tool)
    if not spec:
        log.warning("unknown tool proposed: %s", tool)
        return None
    # dedupe identical pending proposals
    for p in inc.proposals:
        if p.tool == tool and p.args == args and p.approval == m.ApprovalStatus.PENDING:
            return p
    prop = m.ToolProposal(tool=tool, args=args, reason=reason, risk=spec.risk, proposed_by=proposed_by)  # type: ignore[arg-type]
    inc.proposals.append(prop)
    if spec.risk == "safe":
        await execute(inc, prop, approved_by="policy:auto")
    else:
        store._timeline(inc, "approval", f"🛑 Approval required: {tool} {args} — {reason}", prop.id)
        store.broadcast(inc.id, {"type": "approval_required", "proposal": prop.model_dump(mode="json")})
        store.publish_state(inc)
    return prop


async def decide(inc: m.Incident, proposal_id: str, approve: bool, by: str) -> Optional[m.ToolProposal]:
    prop = next((p for p in inc.proposals if p.id == proposal_id), None)
    if not prop or prop.approval != m.ApprovalStatus.PENDING:
        return prop
    prop.decided_at = m.now()
    if approve:
        d = m.Decision(seq=len(inc.decisions) + 1, text=f"Execute {prop.tool} {prop.args}",
                       reason=prop.reason, participants=[by], approved_by=by)
        inc.decisions.append(d)
        store._timeline(inc, "approval", f"✅ {inc.name_of(by)} approved {prop.tool}", prop.id)
        await execute(inc, prop, approved_by=by)
    else:
        prop.approval = m.ApprovalStatus.REJECTED
        prop.approved_by = by
        store._timeline(inc, "approval", f"❌ {inc.name_of(by)} rejected {prop.tool}", prop.id)
        store.publish_state(inc)
    return prop


async def execute(inc: m.Incident, prop: m.ToolProposal, approved_by: str) -> None:
    spec = REGISTRY[prop.tool]
    # policy validation runs again at execution time, never trust the earlier check
    if spec.risk == "critical" and approved_by.startswith("policy:"):
        prop.error = "policy violation: critical tool cannot auto-execute"
        prop.approval = m.ApprovalStatus.REJECTED
        store.publish_state(inc)
        return
    prop.approval = m.ApprovalStatus.APPROVED
    prop.approved_by = approved_by
    try:
        prop.result = await spec.fn(inc, prop.args)
        store._timeline(inc, "tool", f"⚙ {prop.tool} executed → {prop.result.get('summary', 'ok')}", prop.id)
    except Exception as e:
        prop.error = str(e)
        store._timeline(inc, "tool", f"⚙ {prop.tool} FAILED: {e}", prop.id)
    store.publish_state(inc)
