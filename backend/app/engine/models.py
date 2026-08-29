"""Sentinel incident state model.

Everything the AI extracts from the room lands in one of these buckets. The
central design rule: FACT != HYPOTHESIS. Nothing becomes a fact without
evidence, and the AI never promotes a hypothesis on its own certainty.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


def _id() -> str:
    return uuid.uuid4().hex[:10]


def now() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, Enum):
    INCIDENT_COMMANDER = "incident_commander"
    SRE = "sre"
    BACKEND = "backend"
    FRONTEND = "frontend"
    DATABASE = "database"
    SECURITY = "security"
    SUPPORT = "support"
    PRODUCT = "product"
    BUSINESS = "business"
    OBSERVER = "observer"
    UNKNOWN = "unknown"


class Participant(BaseModel):
    uid: str                       # Agora RTC uid (string)
    name: str
    role: Role = Role.UNKNOWN
    focus: str = ""
    role_source: Literal["declared", "inferred", "corrected"] = "declared"
    online: bool = True
    joined_at: datetime = Field(default_factory=now)


class Severity(str, Enum):
    SEV1 = "SEV-1"
    SEV2 = "SEV-2"
    SEV3 = "SEV-3"


class IncidentStatus(str, Enum):
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MITIGATING = "mitigating"
    RECOVERED = "recovered"
    RESOLVED = "resolved"


class Evidence(BaseModel):
    id: str = Field(default_factory=_id)
    source: Literal["monitoring", "participant", "tool", "deployment", "customer"]
    summary: str
    supports: bool = True          # False => contradicts the parent item
    by: Optional[str] = None       # participant uid or system name
    at: datetime = Field(default_factory=now)


class Fact(BaseModel):
    """Evidence-backed statement the team treats as true."""
    id: str = Field(default_factory=_id)
    text: str
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = 0.9
    at: datetime = Field(default_factory=now)


class Observation(BaseModel):
    """Something a participant reported. Not yet verified by a second source."""
    id: str = Field(default_factory=_id)
    text: str
    by: str
    at: datetime = Field(default_factory=now)


class HypothesisStatus(str, Enum):
    UNVERIFIED = "unverified"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class Hypothesis(BaseModel):
    id: str = Field(default_factory=_id)
    text: str
    proposed_by: str
    status: HypothesisStatus = HypothesisStatus.UNVERIFIED
    confidence: float = 0.3
    supporting: list[Evidence] = Field(default_factory=list)
    contradicting: list[Evidence] = Field(default_factory=list)
    at: datetime = Field(default_factory=now)
    last_verified: Optional[datetime] = None


class Decision(BaseModel):
    """Immutable ledger entry."""
    id: str = Field(default_factory=_id)
    seq: int = 0
    text: str
    reason: str = ""
    participants: list[str] = Field(default_factory=list)
    approved_by: Optional[str] = None
    at: datetime = Field(default_factory=now)


class ActionStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"


class Action(BaseModel):
    id: str = Field(default_factory=_id)
    text: str
    owner: Optional[str] = None    # participant uid; None => unowned (Sentinel will chase)
    priority: Priority = Priority.NORMAL
    status: ActionStatus = ActionStatus.OPEN
    created_by: Optional[str] = None
    at: datetime = Field(default_factory=now)
    last_update: datetime = Field(default_factory=now)
    result: Optional[str] = None
    external_ref: Optional[str] = None   # e.g. Jira key


class Conflict(BaseModel):
    id: str = Field(default_factory=_id)
    topic: str
    claim_a: str
    by_a: str
    claim_b: str
    by_b: str
    status: Literal["open", "resolved"] = "open"
    resolution: Optional[str] = None
    at: datetime = Field(default_factory=now)


class Unknown(BaseModel):
    id: str = Field(default_factory=_id)
    question: str
    why_it_matters: str = ""
    status: Literal["open", "answered"] = "open"
    answer: Optional[str] = None
    at: datetime = Field(default_factory=now)


class Risk(BaseModel):
    id: str = Field(default_factory=_id)
    text: str
    severity: Literal["low", "medium", "high"] = "medium"
    status: Literal["open", "mitigated"] = "open"
    at: datetime = Field(default_factory=now)


class TimelineEvent(BaseModel):
    id: str = Field(default_factory=_id)
    at: datetime = Field(default_factory=now)
    kind: Literal[
        "incident", "metric", "hypothesis", "fact", "action", "decision",
        "conflict", "unknown", "risk", "approval", "tool", "sentinel", "participant",
    ]
    text: str
    ref: Optional[str] = None      # id of the related state item


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ToolProposal(BaseModel):
    """A tool call the LLM wants to make. Goes through the gateway."""
    id: str = Field(default_factory=_id)
    tool: str
    args: dict = Field(default_factory=dict)
    reason: str = ""
    risk: Literal["safe", "critical"] = "safe"
    proposed_by: str = "sentinel"
    approval: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: Optional[str] = None
    at: datetime = Field(default_factory=now)
    decided_at: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class ConfidenceMatrix(BaseModel):
    customer_impact: float = 0.0
    outage_scope: float = 0.0
    primary_finding: float = 0.0
    change_correlation: float = 0.0
    root_cause: float = 0.0
    recovery: float = 0.0


class TranscriptLine(BaseModel):
    id: str = Field(default_factory=_id)
    uid: str
    name: str
    text: str
    at: datetime = Field(default_factory=now)
    final: bool = True
    turn_id: Optional[int] = None


class Incident(BaseModel):
    id: str = Field(default_factory=lambda: "INC-" + _id()[:4].upper())
    title: str = "Untitled incident"
    severity: Severity = Severity.SEV1
    status: IncidentStatus = IncidentStatus.INVESTIGATING
    channel: str = ""
    started_at: datetime = Field(default_factory=now)
    resolved_at: Optional[datetime] = None
    impact_summary: str = ""

    participants: dict[str, Participant] = Field(default_factory=dict)
    transcript: list[TranscriptLine] = Field(default_factory=list)

    facts: list[Fact] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    unknowns: list[Unknown] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    proposals: list[ToolProposal] = Field(default_factory=list)
    confidence: ConfidenceMatrix = Field(default_factory=ConfidenceMatrix)

    metrics: dict[str, float] = Field(default_factory=dict)   # latest monitoring snapshot
    agent_id: Optional[str] = None                             # Agora agent id when live
    version: int = 0                                           # bumped on every mutation

    # ---- convenience -------------------------------------------------
    def name_of(self, uid: Optional[str]) -> str:
        if uid is None:
            return "unassigned"
        p = self.participants.get(uid)
        return p.name if p else uid

    def counts(self) -> dict[str, int]:
        return {
            "facts": len(self.facts),
            "hypotheses": len([h for h in self.hypotheses if h.status != HypothesisStatus.REJECTED]),
            "decisions": len(self.decisions),
            "actions": len([a for a in self.actions if a.status != ActionStatus.DONE]),
            "conflicts": len([c for c in self.conflicts if c.status == "open"]),
            "unknowns": len([u for u in self.unknowns if u.status == "open"]),
            "risks": len([r for r in self.risks if r.status == "open"]),
        }
