"use client";
import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import type { TimelineEvent } from "@/lib/types";
import { hhmm } from "@/lib/utils";

const ICON: Record<string, string> = { incident: "🔴", metric: "📊", hypothesis: "💡", fact: "✅", action: "👤", decision: "🧠", conflict: "⚠️", unknown: "❓", risk: "🧨", approval: "🛑", tool: "⚙️", sentinel: "🤖", participant: "🟢" };

export function Timeline({ events }: { events: TimelineEvent[] }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [events.length]);
  return (
    <div className="panel flex h-full flex-col p-4">
      <div className="mb-2 text-xs font-medium tracking-wider text-[var(--muted)]">LIVE INCIDENT TIMELINE</div>
      <ol className="flex-1 space-y-1 overflow-y-auto pr-1">
        {events.map((e) => (
          <motion.li key={e.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} className={`flex gap-2 rounded-md px-2 py-1.5 text-sm ${e.kind === "sentinel" ? "bg-[#142033]" : e.kind === "conflict" || e.kind === "approval" ? "bg-[#2a1a1a]" : ""}`}>
            <span className="w-16 shrink-0 font-mono text-[11px] text-[var(--muted)] tabular-nums">{hhmm(e.at)}</span>
            <span className="w-5 shrink-0">{ICON[e.kind] ?? "•"}</span>
            <span className="flex-1">{e.text}</span>
          </motion.li>
        ))}
        <div ref={end} />
      </ol>
    </div>
  );
}
