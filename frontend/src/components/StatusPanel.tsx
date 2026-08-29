import type { Incident } from "@/lib/types";
import { pct } from "@/lib/utils";

const LABELS: Record<string, string> = { customer_impact: "Customer impact", outage_scope: "Outage scope", primary_finding: "Primary finding", change_correlation: "Change correlation", root_cause: "Root cause", recovery: "Recovery" };

export function StatusPanel({ inc }: { inc: Incident }) {
  const m = inc.metrics;
  const err = m.payment_error_rate ?? 0;
  const overall = inc.confidence.primary_finding;
  return (
    <div className="panel p-4">
      <div className="mb-3 text-xs font-medium tracking-wider text-[var(--muted)]">INCIDENT STATUS</div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <Stat label="Error rate" value={`${err.toFixed(0)}%`} tone={err > 50 ? "red" : err > 10 ? "amber" : "green"} />
        <Stat label="Success" value={`${(m.payment_success_rate ?? 0).toFixed(0)}%`} tone={(m.payment_success_rate ?? 0) < 50 ? "red" : "green"} />
        <Stat label="Confidence" value={pct(overall)} tone={overall > 0.8 ? "green" : "amber"} />
      </div>
      {inc.impact_summary && <div className="mt-3 rounded-md bg-[var(--panel-2)] p-2 text-xs"><span className="text-[var(--muted)]">Impact: </span>{inc.impact_summary}</div>}
      <div className="mt-4 text-xs font-medium tracking-wider text-[var(--muted)]">CONFIDENCE MATRIX</div>
      <ul className="mt-2 space-y-1.5">
        {Object.entries(inc.confidence).map(([k, v]) => (
          <li key={k} className="text-xs">
            <div className="flex justify-between"><span>{LABELS[k] ?? k}</span><span className="tabular-nums text-[var(--muted)]">{pct(v)}</span></div>
            <div className="mt-0.5 h-1.5 rounded bg-[var(--panel-2)]"><div className="h-1.5 rounded transition-all duration-700" style={{ width: pct(v), background: v >= 0.8 ? "var(--green)" : v >= 0.5 ? "var(--amber)" : "var(--red)" }} /></div>
          </li>
        ))}
      </ul>
      {Object.keys(m).length > 0 && (
        <>
          <div className="mt-4 text-xs font-medium tracking-wider text-[var(--muted)]">MONITORING</div>
          <ul className="mt-1 grid grid-cols-2 gap-x-3 text-[11px]">
            {Object.entries(m).map(([k, v]) => <li key={k} className="flex justify-between border-b border-[var(--border)] py-0.5"><span className="text-[var(--muted)]">{k.replace(/_/g, " ")}</span><span className="tabular-nums">{v.toFixed(v > 100 ? 0 : 1)}</span></li>)}
          </ul>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone: "red" | "amber" | "green" }) {
  const c = { red: "var(--red)", amber: "var(--amber)", green: "var(--green)" }[tone];
  return <div className="rounded-md bg-[var(--panel-2)] p-2"><div className="text-xl font-semibold tabular-nums" style={{ color: c }}>{value}</div><div className="text-[10px] text-[var(--muted)]">{label}</div></div>;
}
