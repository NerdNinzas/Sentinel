import { GitBranch } from "lucide-react";
import type { Incident } from "@/lib/types";

/** Evidence graph: each live hypothesis with its supporting (+) and contradicting (−) evidence, drawn as a fan. */
export function EvidenceGraph({ inc }: { inc: Incident }) {
  const hyps = inc.hypotheses.filter((h) => h.status !== "rejected");
  const rowH = 24, colW = 250;
  const rows: Array<{ y: number; h: (typeof hyps)[number]; ev: Array<{ y: number; e: { id: string; source: string; summary: string; supports: boolean } }> }> = [];
  let y = 18;
  for (const h of hyps) {
    const ev = [...h.supporting.map((e) => ({ ...e, supports: true })), ...h.contradicting.map((e) => ({ ...e, supports: false }))];
    const start = y;
    rows.push({ y: start + Math.max(0, (ev.length - 1) * rowH) / 2, h, ev: ev.map((e, i) => ({ y: start + i * rowH, e })) });
    y = start + Math.max(1, ev.length) * rowH + 12;
  }
  const color = (s: string) => (s === "confirmed" ? "var(--green)" : s === "investigating" ? "var(--amber)" : "var(--muted)");
  return (
    <div className="panel p-4">
      <div className="ph"><GitBranch />Evidence graph <span className="ml-auto normal-case tracking-normal text-[var(--dim)]">why Sentinel believes what it believes</span></div>
      {hyps.length === 0 ? <div className="mt-3 text-xs text-[var(--dim)]">No hypotheses yet.</div> : (
        <div className="mt-2 overflow-x-auto"><svg width={colW * 2.4} height={y + 4} className="text-[11px]">
          <defs><filter id="g"><feGaussianBlur stdDeviation="2" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter></defs>
          {rows.map(({ y, h, ev }) => (
            <g key={h.id}>
              <rect x={4} y={y - 11} width={colW - 20} height={22} rx={7} fill="var(--bg-2)" stroke={color(h.status)} />
              <circle cx={14} cy={y} r={3} fill={color(h.status)} filter="url(#g)" />
              <text x={24} y={y + 4} fill="var(--text)">{h.text.slice(0, 32)}{h.text.length > 32 ? "…" : ""}</text>
              <text x={colW - 24} y={y + 4} textAnchor="end" fill={color(h.status)} fontFamily="var(--mono)">{Math.round(h.confidence * 100)}%</text>
              {ev.map(({ y: ey, e }) => (
                <g key={e.id}>
                  <path d={`M${colW - 16} ${y} C ${colW + 6} ${y}, ${colW + 6} ${ey}, ${colW + 22} ${ey}`} stroke={e.supports ? "var(--green)" : "var(--red)"} strokeOpacity={.7} fill="none" />
                  <circle cx={colW + 22} cy={ey} r={3} fill={e.supports ? "var(--green)" : "var(--red)"} />
                  <text x={colW + 30} y={ey + 4} fill="var(--muted)"><tspan fill={e.supports ? "var(--green)" : "var(--red)"} fontWeight={700}>{e.supports ? "+" : "−"}</tspan> <tspan fill="var(--dim)">[{e.source}]</tspan> {String(e.summary).slice(0, 44)}</text>
                </g>
              ))}
              {ev.length === 0 && <text x={colW + 30} y={y + 4} fill="var(--dim)">no evidence yet</text>}
            </g>
          ))}
        </svg></div>
      )}
    </div>
  );
}
