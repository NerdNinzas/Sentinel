"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { Incident } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS: Record<string, string> = { investigating: "bg-[var(--red)]", identified: "bg-[var(--amber)]", mitigating: "bg-[var(--amber)]", recovered: "bg-[var(--green)]", resolved: "bg-[var(--green)]" };

export function Header({ inc, connected, right }: { inc: Incident; connected: boolean; right?: React.ReactNode }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const end = inc.resolved_at ? new Date(inc.resolved_at).getTime() : now;
  const secs = Math.max(0, Math.floor((end - new Date(inc.started_at).getTime()) / 1000));
  const dur = `${String(Math.floor(secs / 60)).padStart(2, "0")}:${String(secs % 60).padStart(2, "0")}`;
  return (
    <header className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--panel)] px-5 py-3">
      <div className="flex items-center gap-3">
        <span className={cn("rounded-md px-2 py-1 text-xs font-bold text-black", inc.severity === "SEV-1" ? "bg-[var(--red)]" : "bg-[var(--amber)]")}>{inc.severity}</span>
        <div>
          <div className="text-lg font-semibold leading-tight">{inc.title}</div>
          <div className="text-xs text-[var(--muted)]">{inc.id} · channel {inc.channel}</div>
        </div>
        <span className="ml-2 font-mono text-lg tabular-nums">{dur}</span>
        <span className={cn("chip flex items-center gap-1 border-transparent text-black", STATUS[inc.status])}>{inc.status}</span>
        {inc.status !== "resolved" && <span className="flex items-center gap-1 text-xs text-[var(--red)]"><span className="pulse inline-block h-2 w-2 rounded-full bg-[var(--red)]" />LIVE</span>}
      </div>
      <div className="flex items-center gap-2">
        <span className={cn("chip", connected ? "text-[var(--green)]" : "text-[var(--red)]")}>{connected ? "ws connected" : "ws reconnecting"}</span>
        {right}
        <Link href={`/incident/${inc.id}/report`} className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--panel-2)]">Report</Link>
      </div>
    </header>
  );
}
