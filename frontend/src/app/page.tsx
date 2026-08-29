"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, ArrowRight, Bot, GitBranch, Lightbulb, ListTodo, Radio, ShieldAlert, ShieldCheck, Siren, Sparkles, Zap } from "lucide-react";
import { api } from "@/lib/api";
import type { Role } from "@/lib/types";
import { cn, roleLabel } from "@/lib/utils";
import { ROLE_ICON } from "@/components/ui";

const ROLES: Role[] = ["incident_commander", "sre", "backend", "frontend", "database", "security", "support", "product", "business", "observer"];
const FEATURES = [
  { Icon: Lightbulb, t: "Facts ≠ hypotheses", d: "“I think the DB is down” never becomes “root cause: DB”. Evidence-backed state only." },
  { Icon: AlertTriangle, t: "Conflict detection", d: "Two responders disagree? Sentinel flags it and asks for verification instead of picking a side." },
  { Icon: ListTodo, t: "Ownership tracking", d: "“Someone check the deploy” gets an owner — or Sentinel chases one." },
  { Icon: ShieldCheck, t: "Human-in-the-loop", d: "Rollbacks, restarts, failovers are proposed, never executed, until a human approves." },
  { Icon: GitBranch, t: "Evidence graph", d: "Every belief shows what supports it, what contradicts it, and how confident the room should be." },
  { Icon: Radio, t: "Lives in the voice room", d: "Joins the Agora channel like a teammate: listens, speaks only when it helps." },
];

export default function Home() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("incident_commander");
  const [title, setTitle] = useState("Payment API Outage");
  const [severity, setSeverity] = useState("SEV-1");
  const [incidents, setIncidents] = useState<Awaited<ReturnType<typeof api.listIncidents>>>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    try { const me = JSON.parse(localStorage.getItem("sentinel.me") || "null"); if (me) { setName(me.name); setRole(me.role); } } catch {}
    api.listIncidents().then(setIncidents).catch((e) => setErr(`Backend unreachable: ${e.message}`));
  }, []);

  const saveMe = () => {
    const uid = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "user";
    localStorage.setItem("sentinel.me", JSON.stringify({ uid, name: name.trim(), role }));
    return { uid, name: name.trim(), role };
  };
  const go = async (id: string) => { setBusy(true); try { const me = saveMe(); await api.join(id, me.uid, me.name, me.role); router.push(`/incident/${id}`); } finally { setBusy(false); } };
  const create = async () => { setBusy(true); try { const inc = await api.createIncident(title, severity); await go(inc.id); } finally { setBusy(false); } };
  const RoleI = ROLE_ICON[role];

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <div className="flex items-center gap-3">
        <span className="glow-blue grid h-12 w-12 place-items-center rounded-2xl bg-[var(--blue)]/15 text-[var(--blue)] ring-1 ring-[var(--blue)]/40"><ShieldAlert className="h-7 w-7" /></span>
        <div><div className="text-[11px] font-semibold tracking-[.25em] text-[var(--muted)]">SENTINEL</div><h1 className="text-3xl font-semibold tracking-tight">AI Incident Commander</h1></div>
        <span className="chip chip-blue ml-auto"><Radio />Agora Conversational AI</span>
      </div>
      <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-[var(--muted)]">The missing intelligence layer inside the incident room. Sentinel joins the war room, separates what the team <b className="text-[var(--text)]">knows</b> from what it <b className="text-[var(--text)]">believes</b>, tracks who owns what, flags contradictions and unknowns — and never touches production without a human.</p>
      {err && <div className="mt-6 flex items-center gap-2 rounded-xl border border-[var(--red)]/50 bg-[var(--red)]/10 p-3 text-sm text-[var(--red)]"><AlertTriangle className="h-4 w-4" />{err} — start it with <code className="mono">uv run uvicorn main:app --reload</code></div>}

      <div className="mt-8 grid grid-cols-[1.1fr_1fr] gap-4">
        <section className="panel p-5">
          <div className="ph"><RoleI />You</div>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" className="input" />
            <select value={role} onChange={(e) => setRole(e.target.value as Role)} className="input">{ROLES.map((r) => <option key={r} value={r}>{roleLabel(r)}</option>)}</select>
          </div>
          <div className="ph mt-6"><Siren />Declare a new incident</div>
          <div className="mt-3 flex gap-2">
            <input value={title} onChange={(e) => setTitle(e.target.value)} className="input flex-1" />
            <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="input">{["SEV-1", "SEV-2", "SEV-3"].map((s) => <option key={s}>{s}</option>)}</select>
          </div>
          <button disabled={!name.trim() || busy} onClick={create} className="btn btn-danger mt-3 w-full justify-center py-2.5 text-[15px]"><Zap />Declare {severity} & open war room<ArrowRight /></button>
          <p className="mt-2 text-center text-[11px] text-[var(--dim)]">Then press <b>Run payment-outage demo</b> or join the voice room and talk.</p>
        </section>

        <section className="panel p-5">
          <div className="ph"><Bot />Active rooms <span className="ml-auto mono normal-case tracking-normal text-[var(--dim)]">{incidents.length}</span></div>
          {incidents.length === 0 ? <div className="mt-6 grid place-items-center text-xs text-[var(--dim)]">No active incidents. Quiet is good.</div> : (
            <ul className="mt-3 space-y-2">
              {incidents.map((i) => (
                <li key={i.id} className="flex items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-2)] p-3">
                  <span className={cn("rounded-md px-1.5 py-0.5 text-[10px] font-bold text-black", i.severity === "SEV-1" ? "bg-[var(--red)]" : "bg-[var(--amber)]")}>{i.severity}</span>
                  <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium">{i.title}</div><div className="mono text-[11px] text-[var(--muted)]">{i.id} · {i.status} · {i.counts.facts} facts · {i.counts.actions} actions</div></div>
                  <button disabled={!name.trim() || busy} onClick={() => go(i.id)} className="btn">Join<ArrowRight /></button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <div className="mt-8 grid grid-cols-3 gap-3">
        {FEATURES.map(({ Icon, t, d }) => (
          <div key={t} className="panel p-4"><div className="flex items-center gap-2 text-sm font-medium"><Icon className="h-4 w-4 text-[var(--blue)]" />{t}</div><p className="mt-1.5 text-[12px] leading-relaxed text-[var(--muted)]">{d}</p></div>
        ))}
      </div>
      <p className="mt-8 flex items-center gap-1.5 text-[11px] text-[var(--dim)]"><Sparkles className="h-3 w-3" />Built for EchoSphere · Agora Conversational AI Hackathon</p>
    </main>
  );
}
