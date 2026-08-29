"use client";
import { useState } from "react";
import type { Incident } from "@/lib/types";
import { cn, pct } from "@/lib/utils";

type Tab = "facts" | "hypotheses" | "actions" | "decisions" | "conflicts" | "unknowns" | "risks";

export function StatePanel({ inc }: { inc: Incident }) {
  const [tab, setTab] = useState<Tab>("hypotheses");
  const n = (uid?: string | null) => (uid ? inc.participants[uid]?.name ?? uid : "unassigned");
  const counts: Record<Tab, number> = {
    facts: inc.facts.length, hypotheses: inc.hypotheses.filter((h) => h.status !== "rejected").length, decisions: inc.decisions.length,
    actions: inc.actions.filter((a) => a.status !== "done").length, conflicts: inc.conflicts.filter((c) => c.status === "open").length,
    unknowns: inc.unknowns.filter((u) => u.status === "open").length, risks: inc.risks.filter((r) => r.status === "open").length,
  };
  return (
    <div className="panel flex h-full flex-col p-4">
      <div className="mb-2 text-xs font-medium tracking-wider text-[var(--muted)]">INCIDENT STATE</div>
      <div className="grid grid-cols-4 gap-1">
        {(Object.keys(counts) as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={cn("rounded-md border px-1.5 py-1 text-[11px] uppercase tracking-wide", tab === t ? "border-[var(--accent)] bg-[#15213a]" : "border-[var(--border)] hover:bg-[var(--panel-2)]", (t === "conflicts" && counts[t] > 0) && "text-[var(--amber)]")}>
            {t} <span className="ml-1 font-mono text-[var(--muted)]">{counts[t]}</span>
          </button>
        ))}
      </div>
      <div className="mt-3 flex-1 space-y-2 overflow-y-auto pr-1 text-sm">
        {tab === "facts" && inc.facts.map((f) => (
          <Card key={f.id}><div className="flex justify-between"><b>✓ {f.text}</b><span className="text-xs text-[var(--muted)]">{pct(f.confidence)}</span></div>
            {f.evidence.map((e) => <div key={e.id} className="mt-1 text-xs text-[var(--muted)]">↳ <span className="chip mr-1">{e.source}</span>{e.summary}</div>)}</Card>))}
        {tab === "hypotheses" && inc.hypotheses.map((h) => (
          <Card key={h.id} className={h.status === "confirmed" ? "border-[var(--green)]" : h.status === "rejected" ? "opacity-50" : ""}>
            <div className="flex items-start justify-between gap-2"><div><span className={cn("chip mr-2", h.status === "confirmed" && "text-[var(--green)]", h.status === "investigating" && "text-[var(--amber)]")}>{h.status}</span>{h.text}</div><span className="shrink-0 text-xs text-[var(--muted)]">{pct(h.confidence)}</span></div>
            <div className="mt-1 text-xs text-[var(--muted)]">proposed by {n(h.proposed_by)}</div>
            {h.supporting.map((e) => <div key={e.id} className="mt-1 text-xs text-[var(--green)]">＋ <span className="chip mr-1">{e.source}</span>{e.summary}</div>)}
            {h.contradicting.map((e) => <div key={e.id} className="mt-1 text-xs text-[var(--red)]">－ <span className="chip mr-1">{e.source}</span>{e.summary}</div>)}
          </Card>))}
        {tab === "actions" && inc.actions.map((a) => (
          <Card key={a.id} className={a.status === "done" ? "opacity-60" : ""}>
            <div className="flex justify-between"><div><span className={cn("chip mr-2", a.priority === "critical" && "text-[var(--red)]")}>{a.priority}</span>{a.text}</div><span className="chip">{a.status.replace("_", " ")}</span></div>
            <div className="mt-1 text-xs text-[var(--muted)]">owner: <b className={a.owner ? "" : "text-[var(--amber)]"}>{n(a.owner)}</b>{a.result && <> · {a.result}</>}</div>
          </Card>))}
        {tab === "decisions" && inc.decisions.map((d) => (
          <Card key={d.id}><b>#{String(d.seq).padStart(2, "0")} {d.text}</b><div className="mt-1 text-xs text-[var(--muted)]">{d.reason}{d.approved_by && <> · approved by {n(d.approved_by)}</>}</div></Card>))}
        {tab === "conflicts" && inc.conflicts.map((c) => (
          <Card key={c.id} className={c.status === "open" ? "border-[var(--amber)]" : "opacity-60"}>
            <div className="text-xs uppercase tracking-wide text-[var(--amber)]">⚠ {c.topic} · {c.status}</div>
            <div className="mt-1"><b>{n(c.by_a)}:</b> “{c.claim_a}”</div><div><b>{n(c.by_b)}:</b> “{c.claim_b}”</div>
            {c.resolution && <div className="mt-1 text-xs text-[var(--muted)]">→ {c.resolution}</div>}
          </Card>))}
        {tab === "unknowns" && inc.unknowns.map((u) => (
          <Card key={u.id} className={u.status === "answered" ? "opacity-60" : ""}><div>? {u.question}</div><div className="mt-1 text-xs text-[var(--muted)]">{u.status === "answered" ? `→ ${u.answer}` : u.why_it_matters}</div></Card>))}
        {tab === "risks" && inc.risks.map((r) => (
          <Card key={r.id}><span className={cn("chip mr-2", r.severity === "high" && "text-[var(--red)]")}>{r.severity}</span>{r.text}</Card>))}
        {counts[tab] === 0 && (tab === "facts" ? inc.facts.length : tab === "decisions" ? inc.decisions.length : 1) === 0 && <div className="text-xs text-[var(--muted)]">Nothing yet.</div>}
      </div>
    </div>
  );
}

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("rounded-md border border-[var(--border)] bg-[var(--panel-2)] p-2.5", className)}>{children}</div>;
}
