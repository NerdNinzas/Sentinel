"use client";
import type { Incident, Role } from "@/lib/types";
import { api } from "@/lib/api";
import { roleLabel } from "@/lib/utils";

const ROLES: Role[] = ["incident_commander", "sre", "backend", "frontend", "database", "security", "support", "product", "business", "observer", "unknown"];

export function Participants({ inc }: { inc: Incident }) {
  const list = Object.values(inc.participants);
  return (
    <div className="panel p-4">
      <div className="mb-2 text-xs font-medium tracking-wider text-[var(--muted)]">PARTICIPANTS</div>
      <ul className="space-y-2">
        {list.map((p) => (
          <li key={p.uid} className="flex items-center gap-2 text-sm">
            <span className={`h-2 w-2 rounded-full ${p.online ? "bg-[var(--green)]" : "bg-[var(--muted)]"}`} />
            <div className="flex-1">
              <div>{p.name} {p.role_source === "inferred" && <span className="chip ml-1 text-[var(--purple)]">inferred</span>}</div>
              <div className="text-[11px] text-[var(--muted)]">{p.focus}</div>
            </div>
            <select value={p.role} onChange={(e) => api.setRole(inc.id, p.uid, e.target.value as Role)} className="rounded border border-[var(--border)] bg-[var(--panel-2)] px-1 py-0.5 text-[11px]">
              {ROLES.map((r) => <option key={r} value={r}>{roleLabel(r)}</option>)}
            </select>
          </li>
        ))}
        <li className="flex items-center gap-2 text-sm"><span className="h-2 w-2 rounded-full bg-[var(--accent)]" /><div className="flex-1"><div>🤖 Sentinel</div><div className="text-[11px] text-[var(--muted)]">AI Commander {inc.agent_id ? "· in voice room" : "· dashboard voice"}</div></div></li>
      </ul>
    </div>
  );
}
