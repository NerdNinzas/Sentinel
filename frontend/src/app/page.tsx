"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Role } from "@/lib/types";
import { roleLabel } from "@/lib/utils";

const ROLES: Role[] = ["incident_commander", "sre", "backend", "frontend", "database", "security", "support", "product", "business", "observer"];

export default function Home() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("incident_commander");
  const [title, setTitle] = useState("Payment API Outage");
  const [severity, setSeverity] = useState("SEV-1");
  const [incidents, setIncidents] = useState<Awaited<ReturnType<typeof api.listIncidents>>>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    try { const me = JSON.parse(localStorage.getItem("sentinel.me") || "null"); if (me) { setName(me.name); setRole(me.role); } } catch {}
    api.listIncidents().then(setIncidents).catch((e) => setErr(`Backend unreachable: ${e.message}`));
  }, []);

  const saveMe = () => {
    const uid = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "user";
    localStorage.setItem("sentinel.me", JSON.stringify({ uid, name: name.trim(), role }));
    return { uid, name: name.trim(), role };
  };

  const go = async (id: string) => { const me = saveMe(); await api.join(id, me.uid, me.name, me.role); router.push(`/incident/${id}`); };
  const create = async () => { const inc = await api.createIncident(title, severity); await go(inc.id); };

  return (
    <main className="mx-auto max-w-3xl px-6 py-14">
      <div className="mb-10">
        <div className="text-xs tracking-[.2em] text-[var(--muted)]">SENTINEL</div>
        <h1 className="mt-1 text-3xl font-semibold">AI Incident Commander</h1>
        <p className="mt-2 text-[var(--muted)]">Joins the war room, separates facts from beliefs, tracks who owns what, flags conflicts — and never runs a production action without a human.</p>
      </div>
      {err && <div className="panel mb-6 border-[var(--red)] p-3 text-sm text-[var(--red)]">{err} — start it with <code>uv run uvicorn main:app --reload</code></div>}

      <section className="panel p-5">
        <h2 className="mb-3 text-sm font-medium text-[var(--muted)]">You</h2>
        <div className="grid grid-cols-2 gap-3">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" className="rounded-md border border-[var(--border)] bg-[var(--panel-2)] px-3 py-2" />
          <select value={role} onChange={(e) => setRole(e.target.value as Role)} className="rounded-md border border-[var(--border)] bg-[var(--panel-2)] px-3 py-2">
            {ROLES.map((r) => <option key={r} value={r}>{roleLabel(r)}</option>)}
          </select>
        </div>
      </section>

      <section className="panel mt-4 p-5">
        <h2 className="mb-3 text-sm font-medium text-[var(--muted)]">Declare a new incident</h2>
        <div className="flex gap-3">
          <input value={title} onChange={(e) => setTitle(e.target.value)} className="flex-1 rounded-md border border-[var(--border)] bg-[var(--panel-2)] px-3 py-2" />
          <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="rounded-md border border-[var(--border)] bg-[var(--panel-2)] px-3 py-2">
            {["SEV-1", "SEV-2", "SEV-3"].map((s) => <option key={s}>{s}</option>)}
          </select>
          <button disabled={!name.trim()} onClick={create} className="rounded-md bg-[var(--red)] px-4 py-2 font-medium text-black disabled:opacity-40">Declare</button>
        </div>
      </section>

      {incidents.length > 0 && (
        <section className="panel mt-4 p-5">
          <h2 className="mb-3 text-sm font-medium text-[var(--muted)]">Join an active room</h2>
          <ul className="divide-y divide-[var(--border)]">
            {incidents.map((i) => (
              <li key={i.id} className="flex items-center justify-between py-2">
                <div><span className="chip mr-2">{i.severity}</span>{i.title} <span className="text-xs text-[var(--muted)]">· {i.id} · {i.status}</span></div>
                <button disabled={!name.trim()} onClick={() => go(i.id)} className="rounded-md border border-[var(--border)] px-3 py-1 text-sm hover:bg-[var(--panel-2)] disabled:opacity-40">Join</button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
