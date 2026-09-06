export type Role =
  | "incident_commander" | "sre" | "backend" | "frontend" | "database" | "security"
  | "support" | "product" | "business" | "observer" | "unknown";

export interface Participant { uid: string; name: string; role: Role; focus: string; role_source: string; online: boolean; joined_at: string; }
export interface Evidence { id: string; source: string; summary: string; supports: boolean; by?: string | null; at: string; }
export interface Fact { id: string; text: string; evidence: Evidence[]; confidence: number; at: string; }
export interface Hypothesis { id: string; text: string; proposed_by: string; status: "unverified" | "investigating" | "confirmed" | "rejected"; confidence: number; supporting: Evidence[]; contradicting: Evidence[]; at: string; last_verified?: string | null; }
export interface Decision { id: string; seq: number; text: string; reason: string; participants: string[]; approved_by?: string | null; at: string; }
export interface Action { id: string; text: string; owner?: string | null; priority: "critical" | "high" | "normal"; status: "open" | "in_progress" | "done" | "blocked"; created_by?: string | null; at: string; last_update: string; result?: string | null; external_ref?: string | null; }
export interface Conflict { id: string; topic: string; claim_a: string; by_a: string; claim_b: string; by_b: string; status: "open" | "resolved"; resolution?: string | null; at: string; }
export interface Unknown { id: string; question: string; why_it_matters: string; status: "open" | "answered"; answer?: string | null; at: string; }
export interface Risk { id: string; text: string; severity: "low" | "medium" | "high"; status: "open" | "mitigated"; at: string; }
export interface TimelineEvent { id: string; at: string; kind: string; text: string; ref?: string | null; }
export interface ToolProposal { id: string; tool: string; args: Record<string, unknown>; reason: string; risk: "safe" | "critical"; proposed_by: string; approval: "pending" | "approved" | "rejected" | "expired"; approved_by?: string | null; at: string; decided_at?: string | null; result?: Record<string, unknown> | null; error?: string | null; }
export interface ConfidenceMatrix { customer_impact: number; outage_scope: number; primary_finding: number; change_correlation: number; root_cause: number; recovery: number; }
export interface TranscriptLine { id: string; uid: string; name: string; text: string; at: string; final: boolean; turn_id?: number | null; }

export interface RepoCommit { sha: string; message: string; author: string; url?: string | null; at?: string | null; minutes_before_incident?: number | null; suspect: boolean; }
export interface RepoPR { number: number; title: string; author: string; url?: string | null; merged_at: string; minutes_before_incident: number; suspect: boolean; }
export interface RepoChanges { repo?: string; branch?: string | null; commits?: RepoCommit[]; merged_prs?: RepoPR[]; failed_runs?: Array<{ name: string; url: string; branch: string; at: string }>; release?: { tag: string; url: string; at: string } | null; error?: string | null; }

export interface Incident {
  id: string; title: string; severity: "SEV-1" | "SEV-2" | "SEV-3";
  status: "investigating" | "identified" | "mitigating" | "recovered" | "resolved";
  channel: string; started_at: string; resolved_at?: string | null; impact_summary: string;
  participants: Record<string, Participant>; transcript: TranscriptLine[];
  facts: Fact[]; observations: unknown[]; hypotheses: Hypothesis[]; decisions: Decision[]; actions: Action[];
  conflicts: Conflict[]; unknowns: Unknown[]; risks: Risk[]; timeline: TimelineEvent[]; proposals: ToolProposal[];
  confidence: ConfidenceMatrix; metrics: Record<string, number>; agent_id?: string | null; version: number;
  repo?: string | null; repo_changes: RepoChanges;
}

export interface ServerConfig { agora_app_id: string; agora_configured: boolean; llm_available: boolean; llm_model: string; demo_mode: boolean; agent_uid: string; }

export type WsMessage =
  | { type: "state"; incident: Incident }
  | { type: "event"; event: TimelineEvent }
  | { type: "transcript"; line: TranscriptLine }
  | { type: "transcript_bulk"; lines: TranscriptLine[] }
  | { type: "sentinel"; text: string; action: string }
  | { type: "metrics"; metrics: Record<string, number> }
  | { type: "approval_required"; proposal: ToolProposal };
