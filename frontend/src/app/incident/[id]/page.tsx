"use client";
import { use, useEffect } from "react";
import { useIncident } from "@/store/useIncident";
import { Header } from "@/components/Header";
import { StatusPanel } from "@/components/StatusPanel";
import { Participants } from "@/components/Participants";
import { Timeline } from "@/components/Timeline";
import { StatePanel } from "@/components/StatePanel";
import { Transcript } from "@/components/Transcript";
import { ApprovalModal } from "@/components/ApprovalModal";
import { VoiceBar } from "@/components/VoiceBar";
import { SentinelBanner } from "@/components/SentinelBanner";
import { EvidenceGraph } from "@/components/EvidenceGraph";
import { Loader2 } from "lucide-react";

export default function IncidentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { incident, transcript, connected, connect, me, setMe } = useIncident();
  useEffect(() => {
    try { const m = JSON.parse(localStorage.getItem("sentinel.me") || "null"); if (m) setMe(m); } catch {}
    return connect(id);
  }, [id, connect, setMe]);
  if (!incident) return <div className="grid h-screen place-items-center text-[var(--muted)]"><span className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" />Connecting to incident {id}…</span></div>;
  return (
    <div className="flex h-screen flex-col">
      <Header inc={incident} connected={connected} />
      <div className="grid flex-1 grid-cols-[290px_1fr_400px] gap-3 overflow-hidden p-3">
        <aside className="flex flex-col gap-3 overflow-y-auto pr-0.5"><StatusPanel inc={incident} /><Participants inc={incident} /></aside>
        <main className="flex min-w-0 flex-col gap-3 overflow-hidden">
          <SentinelBanner lines={transcript} events={incident.timeline} />
          <div className="min-h-0 flex-1"><Timeline events={incident.timeline} /></div>
          <EvidenceGraph inc={incident} />
        </main>
        <aside className="grid grid-rows-[1.1fr_1fr] gap-3 overflow-hidden"><StatePanel inc={incident} /><Transcript incidentId={id} lines={transcript} me={me} /></aside>
      </div>
      <div className="px-3 pb-3"><VoiceBar inc={incident} /></div>
      <ApprovalModal inc={incident} me={me} />
    </div>
  );
}
