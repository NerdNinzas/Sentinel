"""Incident Confidence Matrix — computed from state, never asserted by the LLM."""
from __future__ import annotations

import re
from app.engine import models as m

CAUSAL = re.compile(r"deploy|release|change|config|rollout|commit|version|v\d+\.\d+", re.I)


def compute(inc: m.Incident) -> m.ConfidenceMatrix:
    c = m.ConfidenceMatrix()
    facts = " ".join(f.text.lower() for f in inc.facts)
    mx = inc.metrics

    # customer impact: customer-sourced evidence + metric
    c.customer_impact = 0.0
    if any(e.source == "customer" for f in inc.facts for e in f.evidence):
        c.customer_impact = 0.8
    if mx.get("payment_success_rate", 100) < 50 or "customers" in facts:
        c.customer_impact = max(c.customer_impact, 0.9)
    # customer report + metric-backed payment fact => impact is well established (stays high after recovery)
    if c.customer_impact >= 0.8 and (mx.get("payment_success_rate", 100) < 50 or any("payment success rate" in f.text.lower() for f in inc.facts)):
        c.customer_impact = 0.98

    # outage scope: do we have a metric-backed fact about the failing system?
    c.outage_scope = 0.99 if "payment" in facts and mx else (0.6 if mx else 0.2)

    # primary finding: best hypothesis
    best = max((h for h in inc.hypotheses if h.status != m.HypothesisStatus.REJECTED),
               key=lambda h: h.confidence, default=None)
    c.primary_finding = best.confidence if best else 0.0
    if best and best.status == m.HypothesisStatus.CONFIRMED:
        c.primary_finding = max(c.primary_finding, 0.9)
    open_conflicts = [k for k in inc.conflicts if k.status == "open"]
    if open_conflicts:
        c.primary_finding *= 0.7

    # change correlation: hypotheses about deploys/changes
    causal = [h for h in inc.hypotheses if CAUSAL.search(h.text) and h.status != m.HypothesisStatus.REJECTED]
    c.change_correlation = max((h.confidence for h in causal), default=0.0)

    # root cause: only a confirmed *causal* hypothesis counts; otherwise stays low
    confirmed_causal = [h for h in causal if h.status == m.HypothesisStatus.CONFIRMED]
    if confirmed_causal:
        c.root_cause = max(h.confidence for h in confirmed_causal)
    else:
        c.root_cause = min(0.45, 0.15 + 0.3 * c.change_correlation)

    # recovery
    psr = mx.get("payment_success_rate", 0)
    if inc.status in (m.IncidentStatus.RECOVERED, m.IncidentStatus.RESOLVED):
        c.recovery = 0.94 if psr > 95 else 0.7
    else:
        c.recovery = 0.5 if 50 < psr < 95 else (0.9 if psr > 95 and inc.metrics else 0.05)

    for k, v in c.model_dump().items():
        setattr(c, k, round(max(0.0, min(1.0, v)), 2))
    return c


def spoken_summary(inc: m.Incident) -> str:
    c = inc.confidence
    high = [k for k, v in c.model_dump().items() if v >= 0.85]
    low = [k for k, v in c.model_dump().items() if v < 0.5]
    pretty = lambda ks: ", ".join(k.replace("_", " ") for k in ks)
    if not high:
        return f"Confidence is still low across the board — especially {pretty(low[:3])}."
    return f"We have high confidence about {pretty(high)}" + (f", and low confidence about {pretty(low)}." if low else ".")
