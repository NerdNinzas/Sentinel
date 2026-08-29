"use client";
import { useEffect, useRef, useState } from "react";
import type { TranscriptLine } from "@/lib/types";
import { api } from "@/lib/api";
import { hhmm } from "@/lib/utils";

export function Transcript({ incidentId, lines, me }: { incidentId: string; lines: TranscriptLine[]; me: { uid: string; name: string } | null }) {
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [lines.length]);
  const send = async () => { if (!text.trim() || !me) return; await api.transcript(incidentId, me.uid, text.trim()); setText(""); };
  return (
    <div className="panel flex h-full flex-col p-4">
      <div className="mb-2 text-xs font-medium tracking-wider text-[var(--muted)]">ROOM TRANSCRIPT</div>
      <div className="flex-1 space-y-1.5 overflow-y-auto pr-1 text-sm">
        {lines.map((l) => (
          <div key={l.id} className={`rounded-md px-2 py-1 ${l.uid === "sentinel" ? "border border-[var(--accent)]/40 bg-[#142033]" : ""}`}>
            <span className="mr-2 font-mono text-[10px] text-[var(--muted)]">{hhmm(l.at)}</span>
            <b className={l.uid === "sentinel" ? "text-[var(--accent)]" : ""}>{l.uid === "sentinel" ? "🤖 Sentinel" : l.name}</b>: {l.text}
          </div>
        ))}
        <div ref={end} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); send(); }} className="mt-2 flex gap-2">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder={me ? `Speak as ${me.name} (typed fallback)…` : "Set your name first"} className="flex-1 rounded-md border border-[var(--border)] bg-[var(--panel-2)] px-3 py-1.5 text-sm" />
        <button className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-black">Send</button>
      </form>
    </div>
  );
}
