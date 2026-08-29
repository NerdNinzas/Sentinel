"use client";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Bot, HelpCircle, Lightbulb, MessageCircleQuestion, Megaphone } from "lucide-react";
import type { TranscriptLine, TimelineEvent } from "@/lib/types";
import { Avatar } from "./ui";

const ACTION: Record<string, { Icon: React.ComponentType<{ className?: string }>; cls: string }> = {
  WARN: { Icon: AlertTriangle, cls: "chip-amber" }, ASK: { Icon: HelpCircle, cls: "chip-blue" }, PROPOSE: { Icon: Lightbulb, cls: "chip-red" },
  SUMMARIZE: { Icon: Megaphone, cls: "chip-green" }, CLARIFY: { Icon: MessageCircleQuestion, cls: "chip-purple" },
};

export function SentinelBanner({ lines, events }: { lines: TranscriptLine[]; events: TimelineEvent[] }) {
  const last = [...lines].reverse().find((l) => l.uid === "sentinel");
  if (!last) return null;
  const ev = [...events].reverse().find((e) => e.kind === "sentinel");
  const action = ev?.text.match(/^\[(\w+)\]/)?.[1] ?? "SUMMARIZE";
  const a = ACTION[action] ?? ACTION.SUMMARIZE;
  return (
    <AnimatePresence mode="wait">
      <motion.div key={last.id} initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="glow-blue scan flex items-start gap-3 rounded-2xl border border-[var(--blue)]/40 bg-gradient-to-r from-[#0f1b33] to-[var(--panel)] px-4 py-3">
        <Avatar uid="sentinel" name="Sentinel" size={36} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-[11px] tracking-widest text-[var(--blue)]"><Bot className="h-3.5 w-3.5" />SENTINEL<span className={`chip ${a.cls}`}><a.Icon />{action}</span></div>
          <div className="mt-1 text-[15px] leading-snug">{last.text}</div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
