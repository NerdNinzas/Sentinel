import type { Incident, Role, ServerConfig } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
export const WS_BASE = API_BASE.replace(/^http/, "ws");

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const api = {
  config: () => j<ServerConfig>("/api/config"),
  listIncidents: () => j<Array<{ id: string; title: string; severity: string; status: string; started_at: string; channel: string; counts: Record<string, number> }>>("/api/incidents"),
  createIncident: (title: string, severity: string) => j<Incident>("/api/incidents", { method: "POST", body: JSON.stringify({ title, severity }) }),
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
  report: (id: string) => j<{ markdown: string }>(`/api/incidents/${id}/report`),
};
