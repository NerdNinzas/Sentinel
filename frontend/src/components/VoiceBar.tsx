"use client";
import { useEffect, useState } from "react";
import { Bot, BotOff, Brain, Gauge, Mic, MicOff, PhoneOff, Play, Radio, Square, AlertCircle } from "lucide-react";
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
  const inRoom = status === "live" || status === "browser";
  return (
    <div className="panel flex items-center gap-3 px-4 py-2.5 text-sm">
      <div className="ph"><Radio />Agora voice room</div>
      <span className={cn("chip", status === "live" ? "chip-green" : status === "browser" ? "chip-amber" : status === "connecting" ? "chip-blue" : "")}>
        {inRoom && !muted && <span className="wave flex h-3 items-end"><span /><span /><span /><span /></span>}
        {status === "browser" ? "browser mic · no Agora creds" : status}
      </span>
      {!inRoom ? (
        <button onClick={join} disabled={status === "connecting"} className="btn btn-success"><Mic />Join voice</button>
      ) : (
        <>
          <button onClick={toggleMute} className={cn("btn", muted && "border-[var(--red)] text-[var(--red)]")}>{muted ? <MicOff /> : <Mic />}{muted ? "Unmute" : "Mute"}</button>
          <button onClick={leave} className="btn"><PhoneOff />Leave</button>
        </>
      )}
      {error && <span className="flex items-center gap-1 text-xs text-[var(--red)]"><AlertCircle className="h-3.5 w-3.5" />{error}</span>}
      <div className="mx-1 h-6 w-px bg-[var(--border)]" />
      {inc.agent_id ? (
        <button onClick={() => run("agent", () => api.agentStop(inc.id))} className="btn border-[var(--blue)] text-[var(--blue)]"><BotOff />Remove Sentinel from room</button>
      ) : (
        <button disabled={!cfg?.agora_configured || busy === "agent"} title={cfg?.agora_configured ? "" : "Set AGORA_* creds in backend/.env"} onClick={() => run("agent", () => api.agentStart(inc.id))} className="btn btn-primary"><Bot />Invite Sentinel (Agora agent)</button>
      )}
      <div className="ml-auto flex items-center gap-2">
        <span className="chip"><Brain />{cfg?.llm_available ? cfg.llm_model : "rule-based · no LLM key"}</span>
        <label className="chip"><Gauge /><select value={demoSpeed} onChange={(e) => setDemoSpeed(Number(e.target.value))} className="bg-transparent text-[var(--text)] outline-none">{[1, 2, 4].map((s) => <option key={s} value={s} className="bg-[var(--panel)]">{s}× speed</option>)}</select></label>
        <button onClick={() => run("demo", () => api.demoStart(inc.id, demoSpeed))} className="btn border-[var(--amber)] text-[var(--amber)]"><Play />Run payment-outage demo</button>
        <button onClick={() => run("demo", () => api.demoStop(inc.id))} className="btn btn-ghost" title="Stop demo"><Square /></button>
      </div>
    </div>
  );
}
