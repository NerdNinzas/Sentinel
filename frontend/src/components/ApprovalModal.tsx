"use client";
import { AnimatePresence, motion } from "framer-motion";
import type { Incident } from "@/lib/types";
import { api } from "@/lib/api";

export function ApprovalModal({ inc, me }: { inc: Incident; me: { uid: string; name: string } | null }) {
  const pending = inc.proposals.filter((p) => p.approval === "pending" && p.risk === "critical");
  return (
    <AnimatePresence>
      {pending.map((p) => (
        <motion.div key={p.id} initial={{ y: 40, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 40, opacity: 0 }} className="fixed bottom-6 left-1/2 z-50 w-[560px] -translate-x-1/2 rounded-xl border-2 border-[var(--red)] bg-[var(--panel)] p-5 shadow-2xl">
          <div className="text-xs font-bold tracking-widest text-[var(--red)]">🛑 HUMAN APPROVAL REQUIRED</div>
          <div className="mt-1 text-lg font-semibold">{p.tool.replace(/_/g, " ")}</div>
          <pre className="mt-1 rounded bg-[var(--panel-2)] p-2 text-xs">{JSON.stringify(p.args)}</pre>
          <div className="mt-2 text-sm text-[var(--muted)]">{p.reason}</div>
          <div className="mt-4 flex justify-end gap-2">
            <button onClick={() => me && api.decide(inc.id, p.id, false, me.uid)} className="rounded-md border border-[var(--border)] px-4 py-2 text-sm">Reject</button>
            <button onClick={() => me && api.decide(inc.id, p.id, true, me.uid)} className="rounded-md bg-[var(--green)] px-4 py-2 text-sm font-semibold text-black">Approve as {me?.name ?? "…"}</button>
          </div>
        </motion.div>
      ))}
    </AnimatePresence>
  );
}
