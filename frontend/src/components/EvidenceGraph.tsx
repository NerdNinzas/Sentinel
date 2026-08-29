import type { Incident } from "@/lib/types";

/** Compact evidence graph: each live hypothesis with its supporting (+) and contradicting (−) evidence. */
export function EvidenceGraph({ inc }: { inc: Incident }) {
  const hyps = inc.hypotheses.filter((h) => h.status !== "rejected");
  if (hyps.length === 0) return null;
  const rowH = 26, colW = 240;
  const rows: Array<{ y: number; h: (typeof hyps)[number]; ev: Array<{ y: number; e: any }> }> = [];
  let y = 20;
  for (const h of hyps) {
    const ev = [...h.supporting.map((e) => ({ ...e, supports: true })), ...h.contradicting.map((e) => ({ ...e, supports: false }))];
    const start = y;
    const evs = ev.map((e, i) => ({ y: start + i * rowH, e }));
    rows.push({ y: start + Math.max(0, (ev.length - 1) * rowH) / 2, h, ev: evs });
    y = start + Math.max(1, ev.length) * rowH + 14;
  }
  const color = (s: string) => (s === "confirmed" ? "var(--green)" : s === "investigating" ? "var(--amber)" : "var(--muted)");
  return (
    <div className="panel p-4">
      <div className="mb-1 text-xs font-medium tracking-wider text-[var(--muted)]">EVIDENCE GRAPH</div>
      <div className="overflow-x-auto"><svg width={colW * 2 + 40} height={y + 6} className="text-[11px]">
        {rows.map(({ y, h, ev }) => (
          <g key={h.id}>
            <rect x={4} y={y - 11} width={colW - 20} height={22} rx={6} fill="var(--panel-2)" stroke={color(h.status)} />
            <text x={12} y={y + 4} fill="var(--text)">{h.text.slice(0, 34)}{h.text.length > 34 ? "…" : ""}</text>
            <text x={colW - 24} y={y + 4} textAnchor="end" fill={color(h.status)}>{Math.round(h.confidence * 100)}%</text>
            {ev.map(({ y: ey, e }) => (
              <g key={e.id}>
                <path d={`M${colW - 16} ${y} C ${colW + 4} ${y}, ${colW + 4} ${ey}, ${colW + 20} ${ey}`} stroke={e.supports ? "var(--green)" : "var(--red)"} fill="none" />
                <circle cx={colW + 20} cy={ey} r={3} fill={e.supports ? "var(--green)" : "var(--red)"} />
                <text x={colW + 28} y={ey + 4} fill="var(--muted)"><tspan fill={e.supports ? "var(--green)" : "var(--red)"}>{e.supports ? "+" : "−"}</tspan> [{e.source}] {String(e.summary).slice(0, 40)}</text>
              </g>
            ))}
            {ev.length === 0 && <text x={colW + 28} y={y + 4} fill="var(--muted)">no evidence yet</text>}
          </g>
        ))}
      </svg></div>
    </div>
  );
}
