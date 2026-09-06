"use client";
import { useEffect, useRef, useState } from "react";
import { MessageSquareText, SendHorizonal } from "lucide-react";
import type { TranscriptLine } from "@/lib/types";
import { api } from "@/lib/api";
import { avatarColor, hm } from "@/lib/utils";
import { Avatar } from "./ui";

export function Transcript({ incidentId, lines, me }: { incidentId: string; lines: TranscriptLine[]; me: { uid: string; name: string } | null }) {
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [lines.length]);
  const send = async () => { if (!text.trim() || !me) return; await api.transcript(incidentId, me.uid, text.trim()); setText(""); };
  return (
    <div className="panel flex h-full flex-col p-4">
      <div className="ph"><MessageSquareText />Room transcript</div>
      <div className="mt-3 flex-1 space-y-2 overflow-y-auto pr-1 text-[13px]">
        {lines.map((l) => {
          const ai = l.uid === "sentinel";
          return (
            <div key={l.id} className={`flex items-start gap-2 ${ai ? "rounded-xl border border-[var(--blue)]/30 bg-[var(--blue)]/8 p-2" : ""}`}>
              <Avatar uid={l.uid} name={l.name} size={24} className="mt-0.5" />
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2"><b style={ai ? undefined : { color: avatarColor(l.uid) }} className={ai ? "text-[var(--blue)]" : ""}>{l.name}</b>{l.uid.startsWith("slack-") && <span className="chip chip-purple">SLACK</span>}<span className="mono text-[10px] text-[var(--dim)]">{hm(l.at)}</span></div>
                <div className="leading-snug text-[var(--text)]/90">{l.text}</div>
              </div>
            </div>
          );
        })}
        <div ref={end} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); send(); }} className="mt-2 flex gap-2">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder={me ? `Speak as ${me.name} (typed fallback)…` : "Set your name first"} className="input flex-1 text-[13px]" />
        <button className="btn btn-primary"><SendHorizonal /></button>
      </form>
    </div>
  );
}
