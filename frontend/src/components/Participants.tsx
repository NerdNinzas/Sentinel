"use client";
import { Sparkles, Users, Bot, Mic } from "lucide-react";
import type { Incident, Role } from "@/lib/types";
import { api } from "@/lib/api";
import { roleLabel } from "@/lib/utils";
import { useIncident } from "@/store/useIncident";
import { Avatar, RoleIcon } from "./ui";

const ROLES: Role[] = ["incident_commander", "sre", "backend", "frontend", "database", "security", "support", "product", "business", "observer", "unknown"];

export function Participants({ inc }: { inc: Incident }) {
  const list = Object.values(inc.participants);
  const speaking = useIncident((s) => s.sentinelQueue.length > 0);
  return (
    <div className="panel p-4">
      <div className="ph"><Users />Participants <span className="ml-auto mono normal-case tracking-normal text-[var(--dim)]">{list.length + 1}</span></div>
      <ul className="mt-3 space-y-2.5">
        {list.map((p) => (
          <li key={p.uid} className="flex items-center gap-2.5">
            <div className="relative"><Avatar uid={p.uid} name={p.name} size={32} /><span className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full ring-2 ring-[var(--panel)] ${p.online ? "bg-[var(--green)]" : "bg-[var(--dim)]"}`} /></div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 text-sm font-medium">{p.name}{p.role_source === "inferred" && <span className="chip chip-purple"><Sparkles />inferred</span>}</div>
              <div className="truncate text-[11px] text-[var(--muted)]">{p.focus || roleLabel(p.role)}</div>
            </div>
            <label className="flex items-center gap-1 rounded-lg border border-[var(--border)] bg-[var(--bg-2)] px-1.5 py-1 text-[11px] text-[var(--muted)]">
              <RoleIcon role={p.role} />
              <select value={p.role} onChange={(e) => api.setRole(inc.id, p.uid, e.target.value as Role)} className="bg-transparent text-[11px] text-[var(--text)] outline-none">
                {ROLES.map((r) => <option key={r} value={r} className="bg-[var(--panel)]">{roleLabel(r)}</option>)}
              </select>
            </label>
          </li>
        ))}
        <li className="flex items-center gap-2.5 rounded-lg border border-[var(--blue)]/30 bg-[var(--blue)]/5 p-2">
          <Avatar uid="sentinel" name="Sentinel" size={32} />
          <div className="flex-1"><div className="flex items-center gap-1.5 text-sm font-medium">Sentinel <span className="chip chip-blue"><Bot />AI</span></div><div className="text-[11px] text-[var(--muted)]">{inc.agent_id ? "in Agora voice room" : "dashboard voice"}</div></div>
          {speaking ? <span className="wave flex h-4 items-end"><span /><span /><span /><span /></span> : <Mic className="h-3.5 w-3.5 text-[var(--dim)]" />}
        </li>
      </ul>
    </div>
  );
}
