import type { Incident, Role, ServerConfig } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
export const WS_BASE = API_BASE.replace(/^http/, "ws");

export function session(): string | null {
  try { return localStorage.getItem("sentinel.session"); } catch { return null; }
}

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const s = session();
  const r = await fetch(`${API_BASE}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(s ? { Authorization: `Bearer ${s}` } : {}), ...(init?.headers ?? {}) } });
  if (r.status === 401 && typeof window !== "undefined" && !path.startsWith("/api/auth")) { window.location.href = "/login"; }
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export interface AuthUser {
  id: number | string; login: string; email?: string | null; name?: string | null; avatar_url?: string | null; html_url?: string | null;
  account_type?: "personal" | "organization" | null; onboarded?: boolean;
  org_id?: string | null; org_name?: string | null; org_role?: string | null; org_notice?: string | null;
  github_connected?: boolean; github_login?: string | null;
}
export interface OrgMember { id: string | number; name?: string | null; email?: string | null; login: string; avatar_url?: string | null; org_role?: string | null; github_login?: string | null }
export interface OrgOverview { org: { id: string; name: string; address?: string | null; website?: string | null } | null; members: OrgMember[]; invites: Array<{ token: string; email?: string | null; status: string; invited_by?: string | null }> }
export interface RepoListing { full_name: string; private: boolean; pushed_at?: string; default_branch?: string; description?: string }
export interface RoomEntry { incident_id: string; role: string; kind: string; joined_at?: string; last_seen?: string; title?: string; severity?: string; status?: string; repo?: string | null; counts?: Record<string, number> }

export const api = {
  config: () => j<ServerConfig>("/api/config"),
  listIncidents: () => j<Array<{ id: string; title: string; severity: string; status: string; started_at: string; channel: string; counts: Record<string, number> }>>("/api/incidents"),
  createIncident: (title: string, severity: string, repo?: string) => j<Incident>("/api/incidents", { method: "POST", body: JSON.stringify({ title, severity, repo }) }),
  setRepo: (id: string, repo: string) => j(`/api/incidents/${id}/repo`, { method: "POST", body: JSON.stringify({ repo }) }),
  getIncident: (id: string) => j<Incident>(`/api/incidents/${id}`),
  join: (id: string, uid: string, name: string, role: Role) =>
    j<{ channel: string; app_id: string; uid: string; tokens: { rtc: string; rtm: string } }>(`/api/incidents/${id}/join`, { method: "POST", body: JSON.stringify({ uid, name, role }) }),
  setRole: (id: string, uid: string, role: Role) => j(`/api/incidents/${id}/participants/${uid}/role`, { method: "POST", body: JSON.stringify({ role }) }),
  transcript: (id: string, uid: string, text: string, final = true, turn_id?: number) =>
    j(`/api/incidents/${id}/transcript`, { method: "POST", body: JSON.stringify({ uid, text, final, turn_id }) }),
  decide: (id: string, pid: string, approve: boolean, by: string) =>
    j(`/api/incidents/${id}/proposals/${pid}/decide`, { method: "POST", body: JSON.stringify({ approve, by }) }),
  agentStart: (id: string) => j(`/api/incidents/${id}/agent/start`, { method: "POST" }),
  agentStop: (id: string) => j(`/api/incidents/${id}/agent/stop`, { method: "POST" }),
  demoStart: (id: string, speed = 1) => j(`/api/incidents/${id}/demo/start?speed=${speed}`, { method: "POST" }),
  demoStop: (id: string) => j(`/api/incidents/${id}/demo/stop`, { method: "POST" }),
  resolve: (id: string) => j<Incident>(`/api/incidents/${id}/resolve`, { method: "POST" }),
  endSession: (id: string) => j<Incident>(`/api/incidents/${id}/end`, { method: "POST" }),
  deleteIncident: (id: string) => j<{ deleted: string }>(`/api/incidents/${id}`, { method: "DELETE" }),
  report: (id: string) => j<{ markdown: string }>(`/api/incidents/${id}/report`),
  signup: (email: string, password: string, name: string) => j<{ session: string; user: AuthUser }>("/api/auth/signup", { method: "POST", body: JSON.stringify({ email, password, name }) }),
  login: (email: string, password: string) => j<{ session: string; user: AuthUser }>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  onboard: (payload: { account_type: string; org_name?: string; org_address?: string; org_website?: string }) => j<AuthUser>("/api/auth/onboard", { method: "POST", body: JSON.stringify(payload) }),
  ackNotice: () => j<{ ok: boolean }>("/api/auth/notice-ack", { method: "POST" }),
  orgOverview: () => j<OrgOverview>("/api/org"),
  createInvite: (email?: string) => j<{ token: string; link: string; emailed: boolean; mail_configured: boolean }>("/api/org/invites", { method: "POST", body: JSON.stringify({ email: email || null }) }),
  inviteInfo: (token: string) => j<{ org_name: string; invited_by: string; status: string }>(`/api/invites/${token}`),
  acceptInvite: (token: string) => j<AuthUser>(`/api/invites/${token}/accept`, { method: "POST" }),
  connectGithub: (token: string) => j<AuthUser>("/api/integrations/github", { method: "POST", body: JSON.stringify({ token }) }),
  disconnectGithub: () => j<AuthUser>("/api/integrations/github", { method: "DELETE" }),
  me: () => j<AuthUser>("/api/auth/me"),
  repos: () => j<RepoListing[]>("/api/github/repos"),
  myRooms: () => j<RoomEntry[]>("/api/me/rooms"),
  integrations: () => j<Record<string, { connected: boolean; status?: string; [k: string]: unknown }>>("/api/integrations"),
};
