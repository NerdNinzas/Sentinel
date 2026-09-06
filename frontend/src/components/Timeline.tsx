"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { type LucideIcon, AlertTriangle, KanbanSquare, MessageSquare, BarChart3, Bot, CheckCircle2, Flame, Gavel, HelpCircle, History, Lightbulb, ListTodo, ShieldAlert, Siren, UserPlus, Wrench } from "lucide-react";
import type { TimelineEvent } from "@/lib/types";
import { hhmm } from "@/lib/utils";

const META: Record<string, { Icon: LucideIcon; color: string }> = {
  incident: { Icon: Siren, color: "var(--red)" }, metric: { Icon: BarChart3, color: "var(--cyan)" }, hypothesis: { Icon: Lightbulb, color: "var(--amber)" },
  fact: { Icon: CheckCircle2, color: "var(--green)" }, action: { Icon: ListTodo, color: "var(--blue)" }, decision: { Icon: Gavel, color: "var(--purple)" },
  conflict: { Icon: AlertTriangle, color: "var(--amber)" }, unknown: { Icon: HelpCircle, color: "var(--muted)" }, risk: { Icon: Flame, color: "var(--red)" },
  approval: { Icon: ShieldAlert, color: "var(--red)" }, tool: { Icon: Wrench, color: "var(--cyan)" }, sentinel: { Icon: Bot, color: "var(--blue)" }, participant: { Icon: UserPlus, color: "var(--green)" },
  slack: { Icon: MessageSquare, color: "#E01E5A" }, jira: { Icon: KanbanSquare, color: "#2684FF" },
};

const FILTERS: Array<{ id: string; label: string; kinds: string[] | null }> = [
  { id: "all", label: "ALL", kinds: null },
  { id: "sentinel", label: "SENTINEL", kinds: ["sentinel"] },
  { id: "evidence", label: "EVIDENCE", kinds: ["fact", "hypothesis", "metric", "conflict", "jira", "slack"] },
  { id: "actions", label: "ACTIONS", kinds: ["action", "decision", "approval", "tool"] },
];

export function Timeline({ events }: { events: TimelineEvent[] }) {
  const end = useRef<HTMLDivElement>(null);
  const [filter, setFilter] = useState("all");
  const shown = useMemo(() => {
    const kinds = FILTERS.find((f) => f.id === filter)?.kinds;
    return kinds ? events.filter((e) => kinds.includes(e.kind)) : events;
  }, [events, filter]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [shown.length]);
  return (
    <div className="panel flex h-full flex-col p-4">
      <div className="ph"><History />Live incident timeline
        <span className="ml-auto flex gap-1">
          {FILTERS.map((f) => (
            <button key={f.id} onClick={() => setFilter(f.id)}
              className={`mono px-2 py-0.5 text-[9px] tracking-[.15em] transition-colors ${filter === f.id ? "bg-[var(--accent)] text-black" : "text-[var(--dim)] hover:text-white"}`}>{f.label}</button>
          ))}
        </span>
        <span className="mono normal-case tracking-normal text-[var(--dim)]">{shown.length}</span>
      </div>
      <ol className="rail relative mt-3 flex-1 space-y-0.5 overflow-y-auto pr-1">
        {shown.length === 0 && <div className="mono grid h-24 place-items-center text-[10px] tracking-[.2em] text-[var(--dim)]">NOTHING IN THIS FILTER YET</div>}
        {shown.map((e) => {
          const m = META[e.kind] ?? META.unknown;
          const hi = e.kind === "sentinel" ? "bg-[var(--blue)]/8 border-[var(--blue)]/25" : e.kind === "conflict" || e.kind === "approval" ? "bg-[var(--red)]/8 border-[var(--red)]/25" : e.kind === "decision" ? "bg-[var(--purple)]/8 border-[var(--purple)]/20" : "border-transparent";
          const speech = e.kind === "sentinel" ? e.text.match(/^\[(\w+)\]\s*([\s\S]*)$/) : null;
          return (
            <motion.li key={e.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} className={`relative flex items-start gap-3 rounded-lg border px-2 py-1.5 text-[13px] ${hi}`}>
              <span className="mono w-[68px] shrink-0 pt-0.5 text-[11px] tabular-nums text-[var(--dim)]">{hhmm(e.at)}</span>
              <span className="relative z-10 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-[var(--panel)] ring-1 ring-[var(--border-2)]"><m.Icon className="h-3 w-3" style={{ color: m.color }} /></span>
              <span className="flex-1 leading-snug">
                {speech ? <><span className="chip chip-blue mr-2 align-middle">{speech[1]}</span><span className="text-[var(--text)]">{speech[2]}</span></> : e.text}
              </span>
            </motion.li>
          );
        })}
        <div ref={end} />
      </ol>
    </div>
  );
}
