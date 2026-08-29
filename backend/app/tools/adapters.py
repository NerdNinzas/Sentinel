"""Integration adapters. Each one talks to the real API when configured and
falls back to a realistic mock otherwise, so the demo never blocks on creds."""
from __future__ import annotations

import asyncio
import logging
import random

import httpx

from app.core.config import get_settings
from app.engine import models as m
from app.mock.monitoring import monitoring  # re-exported for the gateway

log = logging.getLogger("sentinel.adapters")


class Slack:
    async def post(self, inc: m.Incident, text: str) -> dict:
        s = get_settings()
        if not s.slack_bot_token:
            log.info("[mock slack] %s: %s", s.slack_channel, text)
            return {"summary": f"posted to {s.slack_channel} (mock)", "text": text, "mock": True}
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post("https://slack.com/api/chat.postMessage",
                             headers={"Authorization": f"Bearer {s.slack_bot_token}"},
                             json={"channel": s.slack_channel, "text": f"*[{inc.id} {inc.severity.value}]* {text}"})
            data = r.json()
            return {"summary": f"posted to {s.slack_channel}", "ok": data.get("ok"), "ts": data.get("ts")}


class Jira:
    def __init__(self) -> None:
        self._n = 100

    async def create(self, inc: m.Incident, summary: str, assignee: str | None, description: str) -> dict:
        s = get_settings()
        if not (s.jira_base_url and s.jira_api_token):
            self._n += 1
            key = f"{s.jira_project_key}-{self._n}"
            return {"summary": f"created {key} (mock)", "key": key, "url": f"https://jira.example.com/browse/{key}", "assignee": assignee, "mock": True}
        async with httpx.AsyncClient(timeout=15, auth=(s.jira_email, s.jira_api_token)) as c:
            r = await c.post(f"{s.jira_base_url}/rest/api/3/issue", json={"fields": {
                "project": {"key": s.jira_project_key}, "summary": f"[{inc.id}] {summary}",
                "issuetype": {"name": "Task"},
                "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": description or summary}]}]},
            }})
            data = r.json()
            key = data.get("key", "?")
            return {"summary": f"created {key}", "key": key, "url": f"{s.jira_base_url}/browse/{key}"}


class PagerDuty:
    async def page(self, inc: m.Incident, team: str, reason: str) -> dict:
        s = get_settings()
        if not s.pagerduty_api_key:
            return {"summary": f"paged {team} on-call (mock)", "team": team, "mock": True}
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post("https://api.pagerduty.com/incidents",
                             headers={"Authorization": f"Token token={s.pagerduty_api_key}",
                                      "Accept": "application/vnd.pagerduty+json;version=2",
                                      "From": s.jira_email or "sentinel@example.com"},
                             json={"incident": {"type": "incident", "title": f"[{inc.id}] {reason or inc.title}",
                                                "service": {"id": s.pagerduty_service_id, "type": "service_reference"}}})
            return {"summary": f"paged {team}", "status": r.status_code}


class Deploy:
    """Mock deployment controller. Rollback drives the mock monitoring to recovery."""

    async def rollback(self, inc: m.Incident, service: str, version: str | None) -> dict:
        await asyncio.sleep(1.5 / monitoring.speed)
        asyncio.create_task(monitoring.recover_over(seconds=10))
        return {"summary": f"rolled back {service} {version or ''} → v4.1".replace("  ", " "), "service": service, "to": "v4.1"}

    async def restart(self, inc: m.Incident, service: str) -> dict:
        await asyncio.sleep(1)
        return {"summary": f"restarted {service}", "pods": random.randint(3, 8)}

    async def failover(self, inc: m.Incident, database: str) -> dict:
        await asyncio.sleep(2)
        return {"summary": f"failed over {database} to replica-b"}

    async def scale(self, inc: m.Incident, service: str, replicas: int) -> dict:
        await asyncio.sleep(1)
        return {"summary": f"scaled {service} to {replicas} replicas"}

    async def disable_flag(self, inc: m.Incident, flag: str) -> dict:
        return {"summary": f"disabled flag {flag}"}


slack, jira, pagerduty, deploy = Slack(), Jira(), PagerDuty(), Deploy()
