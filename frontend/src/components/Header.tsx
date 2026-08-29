"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Activity, Bot, FileText, Radio, ShieldAlert, Siren, Wifi, WifiOff, CheckCircle2, Search, Wrench, HeartPulse } from "lucide-react";
import type { Incident } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS: Record<string, { cls: string; Icon: React.ComponentType<{ className?: string }> }> = {
  investigating: { cls: "chip-red", Icon: Search }, identified: { cls: "chip-amber", Icon: Activity },
  mitigating: { cls: "chip-amber", Icon: Wrench }, recovered: { cls: "chip-green", Icon: HeartPulse }, resolved: { cls: "chip-green", Icon: CheckCircle2 },
};

export function Header({ inc, connected }: { inc: Incident; connected: boolean }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const end = inc.resolved_at ? new Date(inc.resolved_at).getTime() : now;
  const secs = Math.max(0, Math.floor((end - new Date(inc.started_at).getTime()) / 1000));
  const dur = `${String(Math.floor(secs / 60)).padStart(2, "0")}:${String(secs % 60).padStart(2, "0")}`;
  const st = STATUS[inc.status];
  const live = inc.status !== "resolved";
  return (
    <header className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--panel)]/80 px-5 py-2.5 backdrop-blur">
      <div className="flex items-center gap-4">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-[var(--blue)]/15 text-[var(--blue)] ring-1 ring-[var(--blue)]/40"><ShieldAlert className="h-5 w-5" /></span>
          <span className="hidden text-[11px] font-semibold tracking-[.22em] text-[var(--muted)] lg:block">SENTINEL</span>
        </Link>
        <div className="h-8 w-px bg-[var(--border)]" />
        <span className={cn("flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-bold text-black", inc.severity === "SEV-1" ? "bg-[var(--red)] glow-red" : "bg-[var(--amber)]")}><Siren className="h-3.5 w-3.5" />{inc.severity}</span>
        <div>
          <div className="text-[17px] font-semibold leading-tight tracking-tight">{inc.title}</div>
          <div className="mono text-[11px] text-[var(--muted)]">{inc.id} · <Radio className="inline h-3 w-3" /> {inc.channel}</div>
        </div>
        <span className="mono ml-2 text-xl tabular-nums tracking-wider">{dur}</span>
        <span className={cn("chip", st.cls)}><st.Icon className="h-3 w-3" />{inc.status}</span>
        {live && <span className="flex items-center gap-1.5 text-[11px] font-semibold tracking-widest text-[var(--red)]"><span className="pulse inline-block h-2 w-2 rounded-full bg-[var(--red)] shadow-[0_0_8px_var(--red)]" />LIVE</span>}
      </div>
      <div className="flex items-center gap-2">
        {inc.agent_id && <span className="chip chip-blue"><Bot />agent in room</span>}
        <span className={cn("chip", connected ? "chip-green" : "chip-red")}>{connected ? <Wifi /> : <WifiOff />}{connected ? "realtime" : "reconnecting"}</span>
        <Link href={`/incident/${inc.id}/report`} className="btn"><FileText />Report</Link>
      </div>
    </header>
  );
}
