"use client";
/**
 * Voice room hook.
 *  - Joins the Agora RTC channel (mic publish + play remote audio, incl. Sentinel's TTS)
 *  - Subscribes to the RTM channel and forwards Agora `user.transcription` messages
 *    (which carry the speaker uid) to the backend => speaker-attributed transcript
 *  - Fallback when Agora isn't configured: browser SpeechRecognition + speechSynthesis
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useIncident } from "@/store/useIncident";

type Status = "idle" | "connecting" | "live" | "browser" | "error";

export function useAgoraRoom(incidentId: string) {
  const [status, setStatus] = useState<Status>("idle");
  const [muted, setMuted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const me = useIncident((s) => s.me);
  const popSentinel = useIncident((s) => s.popSentinel);
  const queueLen = useIncident((s) => s.sentinelQueue.length);
  const agentLive = useIncident((s) => !!s.incident?.agent_id);
  const rtcRef = useRef<any>(null);
  const trackRef = useRef<any>(null);
  const rtmRef = useRef<any>(null);
  const recRef = useRef<any>(null);

  // Sentinel speech: if the Agora agent is in the room its TTS plays through RTC;
  // otherwise the browser voices it so the demo always talks.
  useEffect(() => {
    if (queueLen === 0) return;
    const msg = popSentinel();
    if (!msg || agentLive || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(msg.text);
    u.rate = 1.05;
    window.speechSynthesis.speak(u);
  }, [queueLen, popSentinel, agentLive]);

  const startBrowserSTT = useCallback(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR || !me) return false;
    const rec = new SR();
    rec.continuous = true; rec.interimResults = false; rec.lang = "en-US";
    rec.onresult = (e: any) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) api.transcript(incidentId, me.uid, e.results[i][0].transcript.trim()).catch(() => {});
      }
    };
    rec.onend = () => { if (recRef.current === rec) { try { rec.start(); } catch {} } };
    rec.start(); recRef.current = rec;
    return true;
  }, [incidentId, me]);

  const join = useCallback(async () => {
    if (!me) return;
    setStatus("connecting"); setError(null);
    try {
      const cfg = await api.config();
      const info = await api.join(incidentId, me.uid, me.name, "unknown");
      if (!cfg.agora_app_id) {
        startBrowserSTT(); setStatus("browser"); return;
      }
      const AgoraRTC = (await import("agora-rtc-sdk-ng")).default;
      AgoraRTC.setLogLevel(3);
      const client = AgoraRTC.createClient({ mode: "rtc", codec: "vp8" });
      client.on("user-published", async (user: any, mediaType: any) => {
        await client.subscribe(user, mediaType);
        if (mediaType === "audio") user.audioTrack?.play();
      });
      await client.join(info.app_id, info.channel, info.tokens.rtc || null, me.uid);
      const track = await AgoraRTC.createMicrophoneAudioTrack();
      await client.publish([track]);
      rtcRef.current = client; trackRef.current = track;

      // RTM: receive the agent's transcript stream with speaker uids
      try {
        const { RTM } = await import("agora-rtm");
        const rtm = new RTM(info.app_id, me.uid, info.tokens.rtm ? { token: info.tokens.rtm } : undefined);
        rtm.addEventListener("message", (ev: any) => {
          try {
            const raw = typeof ev.message === "string" ? ev.message : new TextDecoder().decode(ev.message);
            const msg = JSON.parse(raw);
            if (msg.object === "user.transcription" && msg.final && msg.text) {
              // Only one client (the first joiner) needs to forward; dedupe happens server-side anyway.
              api.transcript(incidentId, String(msg.user_id), msg.text, true, msg.turn_id).catch(() => {});
            }
          } catch { /* chunked/binary datastream messages are ignored */ }
        });
        await rtm.login();
        await rtm.subscribe(info.channel, { withMessage: true, withPresence: true });
        rtmRef.current = rtm;
      } catch (e) { console.warn("RTM unavailable, transcripts rely on browser STT", e); startBrowserSTT(); }
      setStatus("live");
    } catch (e: any) {
      setError(e?.message ?? String(e)); setStatus("error");
    }
  }, [incidentId, me, startBrowserSTT]);

  const leave = useCallback(async () => {
    recRef.current?.stop?.(); recRef.current = null;
    trackRef.current?.close?.(); await rtcRef.current?.leave?.();
    try { await rtmRef.current?.logout?.(); } catch {}
    rtcRef.current = trackRef.current = rtmRef.current = null;
    setStatus("idle");
  }, []);

  const toggleMute = useCallback(async () => {
    const next = !muted; setMuted(next);
    await trackRef.current?.setEnabled?.(!next);
    if (next) recRef.current?.stop?.(); else if (status === "browser") startBrowserSTT();
  }, [muted, status, startBrowserSTT]);

  useEffect(() => () => { leave(); }, [leave]);
  return { status, error, muted, join, leave, toggleMute };
}
