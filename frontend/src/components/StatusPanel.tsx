"use client";
import { Activity, Database, Gauge, TrendingDown, TrendingUp, Users, Clock3 } from "lucide-react";
import type { Incident } from "@/lib/types";
import { pct, tone } from "@/lib/utils";
import { useIncident } from "@/store/useIncident";
import { Sparkline } from "./ui";

const LABELS: Record<string, string> = { customer_impact: "Customer impact", outage_scope: "Outage scope", primary_finding: "Primary finding", change_correlation: "Change correlation", root_cause: "Root cause", recovery: "Recovery" };

export function StatusPanel({ inc }: { inc: Incident }) {
  const history = useIncident((s) => s.history);
  const m = inc.metrics;
  const psr = m.payment_success_rate ?? 0, err = m.payment_error_rate ?? 0, db = m.db_connection_utilization ?? 0;
  const overall = inc.confidence.primary_finding;
  return (
    <div className="panel p-4">
      <div className="ph"><Gauge />Incident status
        {(m.payments_total ?? 0) > 0 && <span className="chip chip-green ml-auto"><span className="pulse inline-block h-1.5 w-1.5 rounded-full bg-[var(--green)]" />LIVE TELEMETRY</span>}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <Tile label="Payment success" value={`${psr.toFixed(0)}%`} color={psr < 50 ? "var(--red)" : psr < 95 ? "var(--amber)" : "var(--green)"} Icon={psr < 95 ? TrendingDown : TrendingUp} spark={history.map((h) => h.psr)} />
        <Tile label="DB connections" value={`${db.toFixed(0)}%`} color={db >= 95 ? "var(--red)" : db > 80 ? "var(--amber)" : "var(--green)"} Icon={Database} spark={history.map((h) => h.db)} />
        <Tile label="Error rate" value={`${err.toFixed(0)}%`} color={err > 50 ? "var(--red)" : err > 10 ? "var(--amber)" : "var(--green)"} Icon={Activity} spark={history.map((h) => h.err)} />
        <Tile label="Finding confidence" value={pct(overall)} color={tone(overall)} Icon={Users} />
      </div>
      {inc.impact_summary && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-[var(--red)]/30 bg-[var(--red)]/5 p-2.5 text-xs">
          <Users className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--red)]" /><div><div className="text-[10px] uppercase tracking-wider text-[var(--red)]">Customer impact</div>{inc.impact_summary}</div>
        </div>
      )}
      <div className="ph mt-5"><Activity />Confidence matrix</div>
      <ul className="mt-2 space-y-2">
        {Object.entries(inc.confidence).map(([k, v]) => (
          <li key={k} className="text-xs">
            <div className="flex justify-between"><span className="text-[var(--text)]">{LABELS[k] ?? k}</span><span className="mono tabular-nums" style={{ color: tone(v) }}>{pct(v)}</span></div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--panel-3)]"><div className="h-full rounded-full transition-all duration-700" style={{ width: pct(v), background: `linear-gradient(90deg, ${tone(v)}88, ${tone(v)})` }} /></div>
          </li>
        ))}
      </ul>
      {Object.keys(m).length > 0 && (
        <>
          <div className="ph mt-5"><Clock3 />Monitoring · live</div>
          <ul className="mono mt-2 grid grid-cols-1 gap-y-1 text-[11px]">
            {Object.entries(m).map(([k, v]) => <li key={k} className="flex justify-between border-b border-[var(--border)]/60 py-0.5"><span className="text-[var(--muted)]">{k.replace(/_/g, " ")}</span><span className="tabular-nums">{v.toFixed(v > 100 ? 0 : 1)}</span></li>)}
          </ul>
        </>
      )}
    </div>
  );
}

function Tile({ label, value, color, Icon, spark }: { label: string; value: string; color: string; Icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>; spark?: number[] }) {
  const hot = color === "var(--red)";
  return (
    <div className={`rounded-sm border p-2.5 transition-colors ${hot ? "border-[var(--red)]/50 bg-[var(--red)]/6" : "border-[var(--border)] bg-[var(--bg-2)]"}`}>
      <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-[var(--muted)]"><span>{label}</span><Icon className="h-3.5 w-3.5" style={{ color }} /></div>
      <div className="mt-1 flex items-end justify-between gap-1">
        <span className="mono text-2xl font-semibold leading-none tabular-nums" style={{ color }}>{value}</span>
        {spark && spark.length > 1 && <Sparkline data={spark} color={color} width={56} height={22} />}
      </div>
    </div>
  );
}
