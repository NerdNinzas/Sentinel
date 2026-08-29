"use client";
import { Fragment } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ShieldAlert, X, Bot, Clock } from "lucide-react";
import type { Incident } from "@/lib/types";
import { api } from "@/lib/api";
import { hhmm } from "@/lib/utils";

export function ApprovalModal({ inc, me }: { inc: Incident; me: { uid: string; name: string } | null }) {
  const pending = inc.proposals.filter((p) => p.approval === "pending" && p.risk === "critical");
  return (
    <AnimatePresence>
      {pending.length > 0 && <motion.div key="bd" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />}
      {pending.map((p) => (
        <motion.div key={p.id} initial={{ y: 40, opacity: 0, scale: .98 }} animate={{ y: 0, opacity: 1, scale: 1 }} exit={{ y: 40, opacity: 0 }} className="glow-red fixed bottom-8 left-1/2 z-50 w-[600px] -translate-x-1/2 rounded-2xl border border-[var(--red)] bg-[var(--panel)] p-5">
          <div className="flex items-center gap-2 text-[11px] font-bold tracking-[.2em] text-[var(--red)]"><ShieldAlert className="h-4 w-4" />HUMAN APPROVAL REQUIRED<span className="chip chip-red ml-auto">critical · production</span></div>
          <div className="mt-2 text-xl font-semibold capitalize">{p.tool.replace(/_/g, " ")}</div>
          <div className="mono mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-lg bg-[var(--bg-2)] p-3 text-xs">
            {Object.entries(p.args).map(([k, v]) => <Fragment key={k}><span className="text-[var(--muted)]">{k}</span><span>{String(v)}</span></Fragment>)}
          </div>
          <div className="mt-3 flex items-start gap-2 text-sm text-[var(--muted)]"><Bot className="mt-0.5 h-4 w-4 shrink-0 text-[var(--blue)]" />{p.reason}</div>
          <div className="mt-1 flex items-center gap-1 text-[11px] text-[var(--dim)]"><Clock className="h-3 w-3" />proposed {hhmm(p.at)} · Sentinel will not execute this without you</div>
          <div className="mt-4 flex justify-end gap-2">
            <button onClick={() => me && api.decide(inc.id, p.id, false, me.uid)} className="btn"><X />Reject</button>
            <button onClick={() => me && api.decide(inc.id, p.id, true, me.uid)} className="btn btn-success"><Check />Approve as {me?.name ?? "…"}</button>
          </div>
        </motion.div>
      ))}
    </AnimatePresence>
  );
}
