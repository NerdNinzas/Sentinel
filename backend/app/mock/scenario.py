"""Scripted demo: the payment outage from the PRD (§24).

Each step is (delay_seconds, kind, payload). The engine consumes these as
if they came from the live Agora room + monitoring, so the entire pipeline
(extraction, conflicts, approvals, tools, recovery, report) is exercised
end-to-end without a microphone.
"""
from __future__ import annotations

PARTICIPANTS = [
    {"uid": "arjun", "name": "Arjun", "role": "incident_commander", "focus": "Coordination"},
    {"uid": "rahul", "name": "Rahul", "role": "backend", "focus": "Payment API"},
    {"uid": "ananya", "name": "Ananya", "role": "sre", "focus": "Infrastructure"},
    {"uid": "priya", "name": "Priya", "role": "unknown", "focus": ""},   # role gets inferred
]

STEPS: list[tuple[float, str, dict]] = [
    (0.0, "metrics", {"phase": "outage", "note": "📊 Payment success rate fell 98.7% → 21%; PagerDuty SEV-1 triggered"}),
    (2.0, "say", {"uid": "arjun", "text": "Okay everyone, Sentinel is in the room. Payment API is down, this is a SEV-1. Let's get a picture of what's going on."}),
    (5.0, "say", {"uid": "priya", "text": "Customers are unable to complete payments. Support queue has over two hundred tickets in the last ten minutes."}),
    (5.0, "say", {"uid": "rahul", "text": "I think the database is overloaded. The payment service is timing out on every query."}),
    (5.0, "say", {"uid": "arjun", "text": "Rahul, check the database connection pool. Ananya, can you pull the infra dashboards?"}),
    (5.0, "say", {"uid": "ananya", "text": "Looking at it now. Database looks healthy from the node level, CPU is fine."}),
    (6.0, "metrics", {"phase": "db_saturated", "note": "📈 Monitoring: DB connection utilization = 100%, pool wait time 4.8s"}),
    (4.0, "say", {"uid": "rahul", "text": "Connection pool is exhausted. Confirmed — every worker is waiting on a connection, pool wait time is almost five seconds."}),
    (6.0, "say", {"uid": "ananya", "text": "Fair, my check was CPU only. Pool exhaustion is real, connections are at 100%."}),
    (5.0, "say", {"uid": "arjun", "text": "Let's freeze all deployments until we understand this. Someone check what changed in the last hour."}),
    (6.0, "say", {"uid": "ananya", "text": "I'll check the deploy history. There was a payment-api deploy, v4.2, about six minutes before the alerts."}),
    (5.0, "say", {"uid": "rahul", "text": "That's my deploy. It probably introduced the retry loop that's eating connections. I suspect v4.2 is the trigger."}),
    (6.0, "say", {"uid": "rahul", "text": "I propose we rollback payment-api v4.2 to v4.1 right now."}),
    (1.0, "await_approval", {"tool": "rollback_deployment"}),
    (10.0, "metrics", {"phase": "recovered", "note": "🟢 Monitoring: payment success rate recovered to 99.1%"}),
    (4.0, "say", {"uid": "priya", "text": "Support is seeing successful payments again, ticket volume is dropping."}),
    (3.0, "say", {"uid": "arjun", "text": "Sentinel, can you give us a status summary?"}),
]
