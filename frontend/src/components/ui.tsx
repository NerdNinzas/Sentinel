"use client";
import { Bot, Code2, Crown, Database, Eye, Headset, Lock, Megaphone, Server, ShieldCheck, Layout, Briefcase, HelpCircle } from "lucide-react";
import type { Role } from "@/lib/types";
import { avatarColor, cn, initials } from "@/lib/utils";

export const ROLE_ICON: Record<Role, React.ComponentType<{ className?: string }>> = {
  incident_commander: Crown, sre: Server, backend: Code2, frontend: Layout, database: Database, security: Lock,
  support: Headset, product: Briefcase, business: Megaphone, observer: Eye, unknown: HelpCircle,
};

export function Avatar({ uid, name, size = 28, className }: { uid: string; name: string; size?: number; className?: string }) {
  if (uid === "sentinel") {
    return <span className={cn("grid shrink-0 place-items-center rounded-lg bg-[var(--blue)]/15 text-[var(--blue)] ring-1 ring-[var(--blue)]/40", className)} style={{ width: size, height: size }}><Bot style={{ width: size * .6, height: size * .6 }} /></span>;
  }
  const c = avatarColor(uid);
  return <span className={cn("grid shrink-0 place-items-center rounded-lg font-semibold", className)} style={{ width: size, height: size, background: `${c}22`, color: c, fontSize: size * .38, boxShadow: `inset 0 0 0 1px ${c}55` }}>{initials(name)}</span>;
}

export function RoleIcon({ role, className }: { role: Role; className?: string }) {
  const I = ROLE_ICON[role] ?? HelpCircle;
  return <I className={cn("h-3.5 w-3.5", className)} />;
}

export function Ring({ value, size = 34, stroke = 3, color }: { value: number; size?: number; stroke?: number; color?: string }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r;
  const col = color ?? (value >= 0.8 ? "var(--green)" : value >= 0.5 ? "var(--amber)" : "var(--red)");
  return (
    <svg width={size} height={size} className="shrink-0 -rotate-90">
      <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--border-2)" strokeWidth={stroke} fill="none" />
      <circle cx={size / 2} cy={size / 2} r={r} stroke={col} strokeWidth={stroke} fill="none" strokeDasharray={c} strokeDashoffset={c * (1 - value)} strokeLinecap="round" className="transition-all duration-700" />
    </svg>
  );
}

export function Sparkline({ data, color = "var(--blue)", width = 90, height = 26 }: { data: number[]; color?: string; width?: number; height?: number }) {
  if (data.length < 2) return <svg width={width} height={height} />;
  const min = Math.min(...data), max = Math.max(...data), span = max - min || 1;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * width},${height - 2 - ((v - min) / span) * (height - 4)}`).join(" ");
  return (
    <svg width={width} height={height} className="shrink-0">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
      <circle cx={width} cy={height - 2 - ((data[data.length - 1] - min) / span) * (height - 4)} r={2} fill={color} />
    </svg>
  );
}

export const Shield = ShieldCheck;
