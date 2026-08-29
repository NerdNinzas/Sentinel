"use client";
import { create } from "zustand";
import type { Incident, TimelineEvent, TranscriptLine, WsMessage } from "@/lib/types";
import { WS_BASE } from "@/lib/api";

interface SentinelMsg { text: string; action: string; at: number }

interface State {
  incident: Incident | null;
  transcript: TranscriptLine[];
  sentinelQueue: SentinelMsg[];
  lastEvent: TimelineEvent | null;
  connected: boolean;
  me: { uid: string; name: string } | null;
  setMe: (me: { uid: string; name: string }) => void;
  connect: (id: string) => () => void;
  popSentinel: () => SentinelMsg | undefined;
}

export const useIncident = create<State>((set, get) => ({
  incident: null, transcript: [], sentinelQueue: [], lastEvent: null, connected: false, me: null,
  setMe: (me) => set({ me }),
  popSentinel: () => { const [h, ...rest] = get().sentinelQueue; if (h) set({ sentinelQueue: rest }); return h; },
  connect: (id) => {
    let ws: WebSocket | null = null; let closed = false; let timer: ReturnType<typeof setTimeout> | undefined;
    const open = () => {
      ws = new WebSocket(`${WS_BASE}/ws/incidents/${id}`);
      ws.onopen = () => set({ connected: true });
      ws.onclose = () => { set({ connected: false }); if (!closed) timer = setTimeout(open, 1500); };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data) as WsMessage;
        switch (msg.type) {
          case "state": set({ incident: msg.incident }); break;
          case "transcript_bulk": set({ transcript: msg.lines }); break;
          case "transcript": set((s) => ({ transcript: [...s.transcript.filter((l) => l.id !== msg.line.id), msg.line].slice(-400) })); break;
          case "event": set({ lastEvent: msg.event }); break;
          case "sentinel": set((s) => ({ sentinelQueue: [...s.sentinelQueue, { text: msg.text, action: msg.action, at: Date.now() }] })); break;
          case "metrics": set((s) => s.incident ? { incident: { ...s.incident, metrics: msg.metrics } } : {}); break;
          default: break;
        }
      };
    };
    open();
    const ping = setInterval(() => ws?.readyState === 1 && ws.send("ping"), 15000);
    return () => { closed = true; clearInterval(ping); clearTimeout(timer); ws?.close(); };
  },
}));
