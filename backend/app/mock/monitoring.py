"""Mock monitoring adapter.

Emits a scripted metric stream for the demo (payment outage) and exposes a
query interface the LLM tools can call. Swap for Prometheus/Datadog later by
implementing the same two methods.
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Optional

MetricCallback = Callable[[dict[str, float]], Awaitable[None]]

BASELINE = {
    "payment_success_rate": 98.7,
    "payment_error_rate": 1.3,
    "db_connection_utilization": 41.0,
    "db_pool_wait_ms": 12.0,
    "db_p95_latency_ms": 38.0,
    "api_p95_latency_ms": 210.0,
    "auth_success_rate": 99.8,
}

OUTAGE = {
    "payment_success_rate": 21.0,
    "payment_error_rate": 79.0,
    "db_connection_utilization": 88.0,     # saturation shows up a few minutes later (see DB_SATURATED)
    "db_pool_wait_ms": 900.0,
    "db_p95_latency_ms": 2900.0,
    "api_p95_latency_ms": 6100.0,
    "auth_success_rate": 99.6,
}

DB_SATURATED = {**OUTAGE, "db_connection_utilization": 100.0, "db_pool_wait_ms": 4800.0}

DEPLOYMENTS = [
    {"service": "payment-api", "version": "v4.2", "at_offset_min": -6,
     "author": "rahul", "summary": "Retry logic for gateway timeouts; pool size unchanged"},
    {"service": "auth-service", "version": "v2.9", "at_offset_min": -190,
     "author": "ananya", "summary": "Token cache TTL bump"},
]


class MockMonitoring:
    def __init__(self) -> None:
        self.current: dict[str, float] = dict(BASELINE)
        self.phase = "baseline"          # baseline | outage | recovering | recovered
        self._subs: list[MetricCallback] = []
        self.started = time.time()
        self.speed = 1.0                 # demo time-scale; >1 makes recovery faster

    def subscribe(self, cb: MetricCallback) -> None:
        self._subs.append(cb)

    async def _emit(self) -> None:
        for cb in list(self._subs):
            await cb(dict(self.current))

    async def set_phase(self, phase: str) -> None:
        self.phase = phase
        if phase == "outage":
            self.current = dict(OUTAGE)
        elif phase == "db_saturated":
            self.current = dict(DB_SATURATED)
        elif phase == "recovering":
            self.current = {k: (BASELINE[k] + OUTAGE[k]) / 2 for k in BASELINE}
        elif phase == "recovered":
            self.current = dict(BASELINE)
            self.current["payment_success_rate"] = 99.1
        else:
            self.current = dict(BASELINE)
        await self._emit()

    async def recover_over(self, seconds: float = 8.0, steps: int = 4) -> None:
        for i in range(1, steps + 1):
            f = i / steps
            self.current = {k: DB_SATURATED[k] + (BASELINE[k] - DB_SATURATED[k]) * f for k in BASELINE}
            self.phase = "recovering" if i < steps else "recovered"
            if i == steps:
                self.current["payment_success_rate"] = 99.1
            await self._emit()
            await asyncio.sleep(seconds / steps / self.speed)

    async def ingest_live(self, health: dict) -> None:
        """Feed real /health data from the deployed service into the same pipeline."""
        psr = float(health.get("payment_success_rate", 100.0))
        self.current = {
            "payment_success_rate": psr,
            "payment_error_rate": round(100 - psr, 1),
            "db_connection_utilization": float(health.get("db_connection_utilization", 0.0)),
            "db_pool_in_use": float(health.get("db_connections_in_use", 0)),
            "db_pool_size": float(health.get("pool_size", 0)),
            "payments_total": float(health.get("payments_total", 0)),
        }
        self.phase = "live"
        await self._emit()

    # ---- tool-facing query API ----------------------------------------
    def query(self, metric: Optional[str] = None) -> dict:
        if metric:
            return {"metric": metric, "value": self.current.get(metric), "phase": self.phase}
        return {"metrics": self.current, "phase": self.phase}

    def recent_deployments(self, service: Optional[str] = None) -> list[dict]:
        rows = DEPLOYMENTS if not service else [d for d in DEPLOYMENTS if d["service"] == service]
        return [{**d, "minutes_before_incident": -d["at_offset_min"]} for d in rows]


monitoring = MockMonitoring()
