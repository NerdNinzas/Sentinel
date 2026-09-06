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

export function GithubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" className={className ?? "h-3.5 w-3.5"} aria-hidden>
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/>
    </svg>
  );
}

export function SlackIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className ?? "h-5 w-5"} aria-hidden>
      <path fill="#E01E5A" d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z"/>
      <path fill="#36C5F0" d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z"/>
      <path fill="#2EB67D" d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zm-1.268 0a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312z"/>
      <path fill="#ECB22E" d="M15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zm0-1.268a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"/>
    </svg>
  );
}

export function JiraIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className ?? "h-5 w-5"} aria-hidden>
      <defs>
        <linearGradient id="jira-a" x1="98%" y1="0%" x2="58%" y2="40%"><stop offset="0" stopColor="#0052CC"/><stop offset="1" stopColor="#2684FF"/></linearGradient>
        <linearGradient id="jira-b" x1="0%" y1="100%" x2="40%" y2="60%"><stop offset="0" stopColor="#0052CC"/><stop offset="1" stopColor="#2684FF"/></linearGradient>
      </defs>
      <path fill="#2684FF" d="M23.013 0H11.455a5.215 5.215 0 0 0 5.215 5.215h2.129v2.057A5.215 5.215 0 0 0 24 12.483V1.005A1.001 1.001 0 0 0 23.013 0z"/>
      <path fill="url(#jira-a)" d="M17.294 5.757H5.736a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058a5.218 5.218 0 0 0 5.215 5.214V6.758a1.001 1.001 0 0 0-1.001-1.001z"/>
      <path fill="url(#jira-b)" d="M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.004-1.005z"/>
    </svg>
  );
}
