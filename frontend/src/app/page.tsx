"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, ArrowUpRight, Radio } from "lucide-react";
import { api } from "@/lib/api";
import type { Role } from "@/lib/types";
import { cn, roleLabel } from "@/lib/utils";

const ROLES: Role[] = ["incident_commander", "sre", "backend", "frontend", "database", "security", "support", "product", "business", "observer"];

const SIGNALS = [
  { no: "01", tag: "STATE ENGINE", t: "Fact Engine", d: "“I think the DB is down” never becomes root cause. Beliefs stay hypotheses until evidence and a human confirm them." },
  { no: "02", tag: "REASONING", t: "Conflict Radar", d: "Two responders disagree — Sentinel flags it and asks for verification instead of picking a side." },
  { no: "03", tag: "COORDINATION", t: "Ownership Chaser", d: "“Someone check the deploy” gets an owner, a priority, and a follow-up when it goes quiet." },
  { no: "04", tag: "SAFETY", t: "Human Gate", d: "Rollbacks, restarts, failovers are proposed — never executed — until a commander approves." },
  { no: "05", tag: "AUDIT", t: "Evidence Graph", d: "Every belief renders what supports it, what contradicts it, and its live confidence." },
  { no: "06", tag: "HONESTY", t: "Confidence Matrix", d: "Six scores computed from state, never asserted by the model. Low root-cause confidence stays low." },
  { no: "07", tag: "MEMORY", t: "Live Timeline", d: "Every fact, action, decision, conflict and tool run becomes an immutable timeline event." },
  { no: "08", tag: "OUTPUT", t: "Auto Postmortem", d: "Impact, findings, decision ledger, unresolved risks — generated the second the incident resolves." },
];

const PIPELINE = [
  { no: "01", t: "SPEAK", d: "Responders talk in the Agora RTC voice room. Sentinel joins as a participant." },
  { no: "02", t: "TRANSCRIBE", d: "Agora's ares ASR converts speech; RTM delivers speaker-attributed transcripts." },
  { no: "03", t: "REASON", d: "The engine + Gemini extract facts, hypotheses, actions, conflicts as typed ops." },
  { no: "04", t: "GATE", d: "Safe tools auto-run. Production actions wait at the human approval gate." },
  { no: "05", t: "SPEAK BACK", d: "WARN · ASK · SUMMARIZE · PROPOSE — voiced into the room via managed TTS." },
];

const SECTIONS = ["hero", "signals", "pipeline", "war-room"];

export default function Home() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("incident_commander");
  const [title, setTitle] = useState("Payment API Outage");
  const [severity, setSeverity] = useState("SEV-1");
  const [repo, setRepo] = useState("NerdNinzas/Sentinel");
  const [incidents, setIncidents] = useState<Awaited<ReturnType<typeof api.listIncidents>>>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [active, setActive] = useState(0);
  const obs = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    try { const me = JSON.parse(localStorage.getItem("sentinel.me") || "null"); if (me) { setName(me.name); setRole(me.role); } } catch {}
    try { setSignedIn(!!localStorage.getItem("sentinel.session")); } catch {}
    api.listIncidents().then((l) => setIncidents(l.filter((i) => i.status !== "resolved"))).catch((e) => setErr(`Backend unreachable: ${e.message}`));
    obs.current = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) setActive(SECTIONS.indexOf(e.target.id)); }), { threshold: 0.4 });
    SECTIONS.forEach((id) => { const el = document.getElementById(id); if (el) obs.current!.observe(el); });
    return () => obs.current?.disconnect();
  }, []);

  const saveMe = () => {
    const uid = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "user";
    localStorage.setItem("sentinel.me", JSON.stringify({ uid, name: name.trim(), role }));
    return { uid, name: name.trim(), role };
  };
  const go = async (id: string) => { if (!signedIn) { router.push("/login"); return; } setBusy(true); try { const me = saveMe(); await api.join(id, me.uid, me.name, me.role); router.push(`/incident/${id}`); } finally { setBusy(false); } };
  const create = async () => { if (!signedIn) { router.push("/login"); return; } setBusy(true); try { const inc = await api.createIncident(title, severity, repo.trim()); await go(inc.id); } catch (e: unknown) { setBusy(false); alert(e instanceof Error ? e.message : String(e)); } };

  return (
    <main className="relative">
      {/* left dot nav */}
      <nav className="fixed left-7 top-1/2 z-30 hidden -translate-y-1/2 flex-col gap-5 md:flex">
        {SECTIONS.map((id, i) => (
          <a key={id} href={`#${id}`} aria-label={id} className="block h-2 w-2 rounded-full transition-all" style={{ background: active === i ? "var(--accent)" : "#333", transform: active === i ? "scale(1.35)" : "none" }} />
        ))}
      </nav>
      <div className="fixed left-0 top-0 z-20 hidden h-full w-[84px] border-r border-[var(--border)] md:block" />

      {/* ============ HERO ============ */}
      <section id="hero" className="relative flex min-h-screen flex-col justify-center px-6 md:pl-36 md:pr-16">
        <div className="label mb-8 flex items-center gap-3"><span className="pulse inline-block h-2 w-2 rounded-full bg-[var(--red)]" />LIVE VOICE SYSTEM — AGORA CONVERSATIONAL AI<span className="text-[var(--dim)]">/ BY NERDNINZAS</span></div>
        <Flap word="SENTINEL" />
        <div className="label mt-8 flex items-center gap-2 text-[var(--dim)]"><Radio className="h-3.5 w-3.5" />AI INCIDENT COMMANDER</div>
        <h1 className="mt-6 max-w-3xl text-4xl font-light text-[#cfd4de] md:text-5xl" style={{ letterSpacing: "-0.01em" }}>
          The intelligence layer inside the incident room.
        </h1>
        <p className="mono mt-8 max-w-xl text-[13px] leading-relaxed text-[var(--muted)]">
          Sentinel joins the war room like a teammate. It separates what the team knows
          from what it believes, tracks who owns what, flags contradictions — and never
          touches production without a human.
        </p>
        <div className="mt-12 flex flex-wrap items-center gap-6">
          <a href={signedIn ? "/dashboard" : "/login"} className="btn">{signedIn ? "OPEN CONSOLE" : "SIGN IN / CREATE ACCOUNT"} <ArrowUpRight /></a>
          <a href="#war-room" className="btn btn-ghost">ENTER WAR ROOM</a>
          <a href="#signals" className="label transition-colors hover:text-[var(--text)]">WHAT IT DOES</a>
        </div>
        <div className="vbadge absolute bottom-8 right-8 hidden md:block">V.01 / ECHOSPHERE BUILD</div>
      </section>

      {/* ============ SIGNALS ============ */}
      <section id="signals" className="relative border-t border-[var(--border)] px-6 py-28 md:pl-36 md:pr-16">
        <span className="absolute right-[28%] top-24 hidden h-9 w-9 rounded-full bg-[var(--accent)] md:block" />
        <div className="label label-accent">01 / SIGNALS</div>
        <h2 className="display mt-4 text-6xl uppercase text-white md:text-7xl">What Sentinel Does</h2>
        <div className="mt-16 grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
          {SIGNALS.map((s) => (
            <article key={s.no} className="sigcard">
              <div className="mono flex items-baseline justify-between text-[10px] tracking-[.2em] text-[var(--dim)]"><span>NO. {s.no}</span><span>{s.tag}</span></div>
              <h3 className="mt-6 text-3xl font-medium tracking-tight text-white">{s.t}</h3>
              <div className="underline" />
              <p className="mono text-[12px] leading-relaxed text-[var(--muted)]">{s.d}</p>
            </article>
          ))}
        </div>
      </section>

      {/* ============ PIPELINE ============ */}
      <section id="pipeline" className="relative border-t border-[var(--border)] px-6 py-28 md:pl-36 md:pr-16">
        <div className="label label-accent">02 / PIPELINE</div>
        <h2 className="display mt-4 text-6xl uppercase text-white md:text-7xl">Life of a Sentence</h2>
        <div className="mt-16 grid grid-cols-1 gap-px overflow-hidden border border-[var(--border)] bg-[var(--border)] md:grid-cols-5">
          {PIPELINE.map((p, i) => (
            <div key={p.no} className="group relative bg-[var(--panel)] p-6 transition-colors hover:bg-[var(--panel-2)]">
              <div className="display text-5xl text-[#2e323b] transition-colors group-hover:text-[var(--accent)]">{p.no}</div>
              <div className="mono mt-5 text-[13px] font-semibold tracking-[.22em] text-white">{p.t}</div>
              <p className="mono mt-3 text-[11.5px] leading-relaxed text-[var(--muted)]">{p.d}</p>
              {i < PIPELINE.length - 1 && <span className="mono absolute right-3 top-6 text-[var(--dim)]">→</span>}
            </div>
          ))}
        </div>
        <p className="mono mt-6 text-[11px] tracking-wider text-[var(--dim)]">ASR: AGORA ARES · LLM: GEMINI 2.5 FLASH (CUSTOM VENDOR → OUR ENGINE) · TTS: AGORA-MANAGED · TRANSCRIPTS: RTM DATA CHANNEL</p>
      </section>

      {/* ============ WAR ROOM ============ */}
      <section id="war-room" className="relative border-t border-[var(--border)] px-6 py-28 md:pl-36 md:pr-16">
        <div className="label label-accent">03 / WAR ROOM</div>
        <h2 className="display mt-4 text-6xl uppercase text-white md:text-7xl">Declare An Incident</h2>
        {!signedIn && (
          <div className="mono mt-8 flex max-w-2xl items-center justify-between gap-4 border border-[var(--accent)]/50 bg-[var(--accent)]/8 p-4 text-[12px] text-[var(--text)]">
            <span>Sign in to declare or join a war room — solo or as an organization workspace with your whole team.</span>
            <a href="/login" className="btn btn-primary btn-sm shrink-0">SIGN IN <ArrowUpRight /></a>
          </div>
        )}
        {err && <div className="mono mt-8 flex max-w-2xl items-center gap-2 border border-[var(--red)]/50 bg-[var(--red)]/8 p-3 text-[12px] text-[var(--red)]"><AlertTriangle className="h-4 w-4 shrink-0" />{err} — start it with `uv run uvicorn main:app`</div>}
        <div className="mt-14 grid grid-cols-1 gap-12 lg:grid-cols-2">
          <div>
            <div className="label mb-5">OPERATOR</div>
            <div className="grid grid-cols-2 gap-3">
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="YOUR NAME" className="input" />
              <select value={role} onChange={(e) => setRole(e.target.value as Role)} className="input">{ROLES.map((r) => <option key={r} value={r}>{roleLabel(r).toUpperCase()}</option>)}</select>
            </div>
            <div className="label mb-5 mt-10">INCIDENT</div>
            <div className="flex gap-3">
              <input value={title} onChange={(e) => setTitle(e.target.value)} className="input flex-1" />
              <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="input">{["SEV-1", "SEV-2", "SEV-3"].map((s) => <option key={s}>{s}</option>)}</select>
            </div>
            <div className="label mb-5 mt-10">LINKED GITHUB REPO — SENTINEL READS RECENT COMMITS & PRS AS EVIDENCE</div>
            <input value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="owner/repo (blank = none)" className="input w-full" />
            <button disabled={!name.trim() || busy} onClick={create} className="btn btn-primary mt-8 w-full justify-center py-4">DECLARE {severity} & OPEN WAR ROOM <ArrowUpRight /></button>
            <p className="mono mt-4 text-center text-[10.5px] tracking-wider text-[var(--dim)]">THEN RUN THE PAYMENT-OUTAGE DEMO — OR JOIN VOICE AND TALK</p>
          </div>
          <div>
            <div className="label mb-5">ACTIVE ROOMS — {incidents.length}</div>
            {incidents.length === 0 ? (
              <div className="sigcard grid h-48 place-items-center"><span className="mono text-[11px] tracking-[.2em] text-[var(--dim)]">NO ACTIVE INCIDENTS. QUIET IS GOOD.</span></div>
            ) : (
              <ul className="space-y-3">
                {incidents.map((i) => (
                  <li key={i.id} className="sigcard flex items-center gap-5 !py-5">
                    <span className={cn("mono px-2 py-1 text-[10px] font-bold tracking-widest", i.severity === "SEV-1" ? "bg-[var(--red)] text-black" : "bg-[var(--amber)] text-black")}>{i.severity}</span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-lg font-medium text-white">{i.title}</div>
                      <div className="mono text-[10.5px] tracking-wider text-[var(--muted)]">{i.id} · {i.status.toUpperCase()} · {i.counts.facts} FACTS · {i.counts.actions} ACTIONS</div>
                    </div>
                    <button disabled={!name.trim() || busy} onClick={() => go(i.id)} className="btn btn-sm">JOIN <ArrowUpRight /></button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>

      <footer className="flex flex-col items-start justify-between gap-4 border-t border-[var(--border)] px-6 py-10 md:flex-row md:items-center md:pl-36 md:pr-8">
        <span className="label">SENTINEL — BUILT BY NERDNINZAS · ECHOSPHERE / AGORA CONVERSATIONAL AI HACKATHON</span>
        <span className="vbadge">V.01 / EXPERIMENTAL BUILD</span>
      </footer>
    </main>
  );
}

function Flap({ word }: { word: string }) {
  return (
    <div className="flex w-full max-w-[1400px] border border-[var(--border)] bg-black">
      {word.split("").map((ch, i) => (
        <div key={i} className="flap aspect-[0.72] flex-1" style={{ ["--i" as string]: i }}>
          <span className="text-[clamp(3rem,10.5vw,10rem)]">{ch}</span>
        </div>
      ))}
    </div>
  );
}
