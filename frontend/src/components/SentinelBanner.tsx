"use client";
import { AnimatePresence, motion } from "framer-motion";
import type { TranscriptLine } from "@/lib/types";

export function SentinelBanner({ lines }: { lines: TranscriptLine[] }) {
  const last = [...lines].reverse().find((l) => l.uid === "sentinel");
  if (!last) return null;
  return (
    <AnimatePresence mode="wait">
      <motion.div key={last.id} initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="rounded-xl border border-[var(--accent)]/50 bg-gradient-to-r from-[#132039] to-[#101828] px-4 py-3 text-sm">
        <span className="mr-2 text-[var(--accent)]">🤖 Sentinel</span>{last.text}
      </motion.div>
    </AnimatePresence>
  );
}
