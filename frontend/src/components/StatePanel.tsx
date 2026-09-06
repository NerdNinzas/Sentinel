"use client";
import { useState } from "react";
import { AlertTriangle, CheckCircle2, Flame, Gavel, HelpCircle, Layers, Lightbulb, ListTodo, ThumbsDown, ThumbsUp, User } from "lucide-react";
import type { Incident } from "@/lib/types";
import { cn, pct, tone } from "@/lib/utils";
import { Avatar, Ring } from "./ui";

type Tab = "facts" | "hypotheses" | "actions" | "decisions" | "conflicts" | "unknowns" | "risks";
const TABS: Array<{ id: Tab; Icon: React.ComponentType<{ className?: string }>; label: string }> = [
  { id: "facts", Icon: CheckCircle2, label: "Facts" }, { id: "hypotheses", Icon: Lightbulb, label: "Hypotheses" }, { id: "actions", Icon: ListTodo, label: "Actions" },
  { id: "decisions", Icon: Gavel, label: "Decisions" }, { id: "conflicts", Icon: AlertTriangle, label: "Conflicts" }, { id: "unknowns", Icon: HelpCircle, label: "Unknowns" }, { id: "risks", Icon: Flame, label: "Risks" },
];

export function StatePanel({ inc }: { inc: Incident }) {
  const [tab, setTab] = useState<Tab>("hypotheses");
  const n = (uid?: string | null) => (uid ? inc.participants[uid]?.name ?? uid : "unassigned");
  const counts: Record<Tab, number> = {
    facts: inc.facts.length, hypotheses: inc.hypotheses.filter((h) => h.status !== "rejected").length, decisions: inc.decisions.length,
    actions: inc.actions.filter((a) => a.status !== "done").length, conflicts: inc.conflicts.filter((c) => c.status === "open").length,
    unknowns: inc.unknowns.filter((u) => u.status === "open").length, risks: inc.risks.filter((r) => r.status === "open").length,
  };
  const total: Record<Tab, number> = { ...counts, actions: inc.actions.length, conflicts: inc.conflicts.length, unknowns: inc.unknowns.length, risks: inc.risks.length };
  const Ev = ({ e, plus }: { e: { id: string; source: string; summary: string }; plus: boolean }) => (
    <div className="mt-1.5 flex items-start gap-1.5 text-[11px] text-[var(--muted)]">{plus ? <ThumbsUp className="mt-0.5 h-3 w-3 shrink-0 text-[var(--green)]" /> : <ThumbsDown className="mt-0.5 h-3 w-3 shrink-0 text-[var(--red)]" />}<span><span className="chip mr-1">{e.source}</span>{e.summary}</span></div>
  );
  return (
    <div className="panel flex h-full flex-col p-4">
      <div className="ph"><Layers />Incident state</div>
      <div className="mt-3 grid grid-cols-4 gap-1">
        {TABS.map(({ id, Icon, label }) => (
          <button key={id} onClick={() => setTab(id)} className={cn("flex items-center justify-between gap-1 border px-2 py-1.5 font-sans text-[10.5px] transition", tab === id ? "border-[var(--blue)] bg-[var(--blue)]/10 text-[var(--text)]" : "border-[var(--border)] text-[var(--muted)] hover:bg-[var(--panel-2)]", id === "conflicts" && counts[id] > 0 && "text-[var(--amber)] border-[var(--amber)]/50")}>
            <span className="flex min-w-0 items-center gap-1"><Icon className="h-3 w-3 shrink-0" />{label}</span><span className="mono text-[var(--dim)]">{counts[id]}</span>
          </button>
        ))}
      </div>
      <div className="mt-3 flex-1 space-y-2 overflow-y-auto pr-1 text-[13px]">
        {tab === "facts" && inc.facts.map((f) => (
          <Card key={f.id} accent="var(--green)"><div className="flex items-start gap-2"><Ring value={f.confidence} size={30} /><div className="flex-1"><div className="font-medium">{f.text}</div>{f.evidence.map((e) => <Ev key={e.id} e={e} plus={e.supports} />)}</div></div></Card>))}
        {tab === "hypotheses" && inc.hypotheses.map((h) => (
          <Card key={h.id} accent={h.status === "confirmed" ? "var(--green)" : h.status === "investigating" ? "var(--amber)" : "var(--dim)"} className={h.status === "rejected" ? "opacity-50" : ""}>
            <div className="flex items-start gap-2"><Ring value={h.confidence} size={30} />
              <div className="flex-1"><div className="flex flex-wrap items-center gap-1.5"><span className={cn("chip", h.status === "confirmed" && "chip-green", h.status === "investigating" && "chip-amber")}>{h.status}</span><span className="font-medium">{h.text}</span></div>
                <div className="mt-1 flex items-center gap-1 text-[11px] text-[var(--muted)]"><Avatar uid={h.proposed_by} name={n(h.proposed_by)} size={14} /> proposed by {n(h.proposed_by)} · {pct(h.confidence)}</div>
                {h.supporting.map((e) => <Ev key={e.id} e={e} plus />)}{h.contradicting.map((e) => <Ev key={e.id} e={e} plus={false} />)}
              </div></div>
          </Card>))}
        {tab === "actions" && inc.actions.map((a) => (
          <Card key={a.id} accent={a.status === "done" ? "var(--green)" : a.owner ? "var(--blue)" : "var(--amber)"} className={a.status === "done" ? "opacity-60" : ""}>
            <div className="flex items-start justify-between gap-2"><div><span className={cn("chip mr-1.5", a.priority === "critical" && "chip-red", a.priority === "high" && "chip-amber")}>{a.priority}</span>{a.text}</div><span className={cn("chip", a.status === "done" && "chip-green", a.status === "in_progress" && "chip-blue")}>{a.status.replace("_", " ")}</span></div>
            <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-[var(--muted)]">{a.owner ? <Avatar uid={a.owner} name={n(a.owner)} size={16} /> : <User className="h-3.5 w-3.5 text-[var(--amber)]" />}<b className={a.owner ? "text-[var(--text)]" : "text-[var(--amber)]"}>{n(a.owner)}</b>{a.result && <span>· {a.result}</span>}</div>
          </Card>))}
        {tab === "decisions" && inc.decisions.map((d) => (
          <Card key={d.id} accent="var(--purple)"><div className="flex items-start gap-2"><span className="mono text-[var(--purple)]">#{String(d.seq).padStart(2, "0")}</span><div><div className="font-medium">{d.text}</div><div className="mt-0.5 text-[11px] text-[var(--muted)]">{d.reason}{d.approved_by && <> · <Gavel className="inline h-3 w-3" /> {n(d.approved_by)}</>}</div></div></div></Card>))}
        {tab === "conflicts" && inc.conflicts.map((c) => (
          <Card key={c.id} accent={c.status === "open" ? "var(--amber)" : "var(--dim)"} className={c.status === "resolved" ? "opacity-70" : ""}>
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-[var(--amber)]"><AlertTriangle className="h-3 w-3" />{c.topic} · {c.status}</div>
            <div className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-2 gap-y-1"><Avatar uid={c.by_a} name={n(c.by_a)} size={18} /><span>“{c.claim_a}”</span><Avatar uid={c.by_b} name={n(c.by_b)} size={18} /><span>“{c.claim_b}”</span></div>
            {c.resolution && <div className="mt-1.5 text-[11px] text-[var(--green)]">→ {c.resolution}</div>}
          </Card>))}
        {tab === "unknowns" && inc.unknowns.map((u) => (
          <Card key={u.id} accent={u.status === "answered" ? "var(--green)" : "var(--muted)"} className={u.status === "answered" ? "opacity-70" : ""}><div className="flex items-start gap-2"><HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--muted)]" /><div><div className="font-medium">{u.question}</div><div className="mt-0.5 text-[11px] text-[var(--muted)]">{u.status === "answered" ? <span className="text-[var(--green)]">→ {u.answer}</span> : u.why_it_matters}</div></div></div></Card>))}
        {tab === "risks" && inc.risks.map((r) => (
          <Card key={r.id} accent={r.severity === "high" ? "var(--red)" : "var(--amber)"}><div className="flex items-center gap-2"><Flame className="h-4 w-4 shrink-0" style={{ color: r.severity === "high" ? "var(--red)" : "var(--amber)" }} /><span className={cn("chip", r.severity === "high" ? "chip-red" : "chip-amber")}>{r.severity}</span>{r.text}</div></Card>))}
        {total[tab] === 0 && <div className="grid h-32 place-items-center text-xs text-[var(--dim)]">Nothing here yet — Sentinel is listening.</div>}
      </div>
    </div>
  );
}

function Card({ children, className, accent }: { children: React.ReactNode; className?: string; accent: string }) {
  return <div className={cn("rounded-xl border border-[var(--border)] bg-[var(--bg-2)] p-2.5", className)} style={{ borderLeft: `3px solid ${accent}` }}>{children}</div>;
}
