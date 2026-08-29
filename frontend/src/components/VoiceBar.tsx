"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Incident, ServerConfig } from "@/lib/types";
import { useAgoraRoom } from "@/hooks/useAgoraRoom";
import { cn } from "@/lib/utils";

export function VoiceBar({ inc }: { inc: Incident }) {
  const { status, error, muted, join, leave, toggleMute } = useAgoraRoom(inc.id);
  const [cfg, setCfg] = useState<ServerConfig | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [demoSpeed, setDemoSpeed] = useState(1);
  useEffect(() => { api.config().then(setCfg).catch(() => {}); }, []);
  const run = async (k: string, fn: () => Promise<unknown>) => { setBusy(k); try { await fn(); } catch (e: any) { alert(e.message); } finally { setBusy(null); } };
  return (
    <div className="panel flex items-center gap-3 px-4 py-2.5 text-sm">
      <div className="text-xs font-medium tracking-wider text-[var(--muted)]">AGORA VOICE ROOM</div>
      <span className={cn("chip", status === "live" ? "text-[var(--green)]" : status === "browser" ? "text-[var(--amber)]" : "")}>{status === "browser" ? "browser mic (no Agora creds)" : status}</span>
      {status === "idle" || status === "error" ? (
        <button onClick={join} className="rounded-md bg-[var(--green)] px-3 py-1 font-medium text-black">🎙 Join voice</button>
      ) : (
        <>
          <button onClick={toggleMute} className="rounded-md border border-[var(--border)] px-3 py-1">{muted ? "Unmute" : "Mute"}</button>
          <button onClick={leave} className="rounded-md border border-[var(--border)] px-3 py-1">Leave</button>
        </>
      )}
      {error && <span className="text-xs text-[var(--red)]">{error}</span>}
      <div className="mx-2 h-5 w-px bg-[var(--border)]" />
      {inc.agent_id ? (
        <button onClick={() => run("agent", () => api.agentStop(inc.id))} className="rounded-md border border-[var(--accent)] px-3 py-1 text-[var(--accent)]">🤖 Sentinel in room · stop</button>
      ) : (
        <button disabled={!cfg?.agora_configured || busy === "agent"} title={cfg?.agora_configured ? "" : "Set AGORA_* creds in backend/.env"} onClick={() => run("agent", () => api.agentStart(inc.id))} className="rounded-md bg-[var(--accent)] px-3 py-1 font-medium text-black disabled:opacity-40">🤖 Invite Sentinel (Agora agent)</button>
      )}
      <div className="ml-auto flex items-center gap-2 text-xs">
        <span className="chip">{cfg?.llm_available ? `LLM: ${cfg.llm_model}` : "LLM: rule-based (no key)"}</span>
        <select value={demoSpeed} onChange={(e) => setDemoSpeed(Number(e.target.value))} className="rounded border border-[var(--border)] bg-[var(--panel-2)] px-1 py-0.5">
          {[1, 2, 4].map((s) => <option key={s} value={s}>{s}× speed</option>)}
        </select>
        <button onClick={() => run("demo", () => api.demoStart(inc.id, demoSpeed))} className="rounded-md border border-[var(--amber)] px-3 py-1 text-[var(--amber)]">▶ Run payment-outage demo</button>
        <button onClick={() => run("demo", () => api.demoStop(inc.id))} className="rounded-md border border-[var(--border)] px-2 py-1">■</button>
      </div>
    </div>
  );
}
