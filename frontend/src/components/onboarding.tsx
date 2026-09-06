"use client";
import { useState } from "react";
import { ArrowRight, ArrowUpRight, Building2, Check, Gauge, Loader2, Plug, Settings2, Siren, UserRound, Users } from "lucide-react";
import { api, type AuthUser } from "@/lib/api";
import { cn } from "@/lib/utils";

/* ---------- first-run onboarding: personal vs organization ---------- */
export function OnboardingModal({ user, onDone }: { user: AuthUser; onDone: (u: AuthUser) => void }) {
  const [step, setStep] = useState<"type" | "org">("type");
  const [choice, setChoice] = useState<"personal" | "organization" | null>(null);
  const [orgName, setOrgName] = useState("");
  const [orgAddress, setOrgAddress] = useState("");
  const [orgWebsite, setOrgWebsite] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const finish = async (type: "personal" | "organization") => {
    setBusy(true); setErr(null);
    try {
      const u = await api.onboard({ account_type: type, org_name: orgName, org_address: orgAddress, org_website: orgWebsite });
      onDone(u);
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-[90] grid place-items-center bg-black/70 backdrop-blur-sm p-6">
      <div className="glow-blue w-full max-w-xl border border-[var(--accent)]/40 bg-[var(--panel)] p-8">
        <div className="mono text-[10px] tracking-[.3em] text-[var(--accent)]">WELCOME TO SENTINEL, {(user.name || "").split(" ")[0].toUpperCase()}</div>
        {step === "type" && (
          <>
            <h2 className="display mt-2 text-4xl uppercase">How will you use it?</h2>
            <div className="mt-6 grid grid-cols-2 gap-4">
              {([
                { id: "personal" as const, Icon: UserRound, t: "Personal use", d: "Solo war rooms. Your incidents, your repos, your reports." },
                { id: "organization" as const, Icon: Building2, t: "Organization workspace", d: "Invite your team, share war rooms, respond to incidents together." },
              ]).map(({ id, Icon, t, d }) => (
                <button key={id} onClick={() => setChoice(id)}
                  className={cn("border p-5 text-left transition-all", choice === id ? "border-[var(--accent)] bg-[var(--accent)]/10" : "border-[var(--border-2)] hover:border-[var(--muted)]")}>
                  <Icon className={cn("h-6 w-6", choice === id ? "text-[var(--accent)]" : "text-[var(--muted)]")} />
                  <div className="mt-3 font-medium text-white">{t}</div>
                  <p className="mono mt-1.5 text-[11px] leading-relaxed text-[var(--muted)]">{d}</p>
                </button>
              ))}
            </div>
            <button disabled={!choice || busy} onClick={() => (choice === "organization" ? setStep("org") : finish("personal"))}
              className="btn btn-primary mt-6 w-full justify-center py-3">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}CONTINUE <ArrowRight />
            </button>
          </>
        )}
        {step === "org" && (
          <>
            <h2 className="display mt-2 text-4xl uppercase">Your organization</h2>
            <div className="label mb-2 mt-6">ORGANIZATION NAME *</div>
            <input value={orgName} onChange={(e) => setOrgName(e.target.value)} placeholder="NerdNinzas" className="input w-full" />
            <div className="label mb-2 mt-5">ADDRESS</div>
            <input value={orgAddress} onChange={(e) => setOrgAddress(e.target.value)} placeholder="New Delhi, IN" className="input w-full" />
            <div className="label mb-2 mt-5">WEBSITE</div>
            <input value={orgWebsite} onChange={(e) => setOrgWebsite(e.target.value)} placeholder="https://…" className="input w-full" />
            <div className="mt-6 flex gap-3">
              <button onClick={() => setStep("type")} className="btn">BACK</button>
              <button disabled={!orgName.trim() || busy} onClick={() => finish("organization")} className="btn btn-primary flex-1 justify-center">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Building2 className="h-4 w-4" />}CREATE WORKSPACE <ArrowUpRight />
              </button>
            </div>
          </>
        )}
        {err && <div className="mono mt-3 text-[11px] text-[var(--red)]">{err}</div>}
      </div>
    </div>
  );
}

/* ---------- guided tour tooltips ---------- */
const STEPS = [
  { view: "overview", Icon: Gauge, t: "Overview", d: "Your mission control — live incidents, SEV-1s burning, and the rooms you've been part of." },
  { view: "rooms", Icon: Siren, t: "War Rooms", d: "Declare an incident, link a GitHub repo as evidence, and Sentinel joins the room listening." },
  { view: "integrations", Icon: Plug, t: "Integrations", d: "Connect GitHub for repo evidence, Slack for status updates, Jira for follow-up tasks." },
  { view: "team", Icon: Users, t: "Team", d: "Invite teammates by email or link. Everyone in the workspace shares war rooms and reports." },
  { view: "settings", Icon: Settings2, t: "Settings", d: "Your plan, trial period, voice and AI preferences — and the always-on human approval gate." },
];

export function TourOverlay({ setView, onDone }: { setView: (v: string) => void; onDone: () => void }) {
  const [i, setI] = useState(0);
  const step = STEPS[i];
  const next = () => {
    if (i + 1 >= STEPS.length) { onDone(); return; }
    setView(STEPS[i + 1].view); setI(i + 1);
  };
  return (
    <div className="fixed inset-0 z-[80] bg-black/50" onClick={onDone}>
      <div onClick={(e) => e.stopPropagation()}
        className="fixed bottom-8 left-1/2 w-[440px] -translate-x-1/2 border border-[var(--accent)]/50 bg-[var(--panel)] p-5 shadow-[0_20px_60px_rgba(0,0,0,.6)]">
        <div className="flex items-center gap-2">
          <step.Icon className="h-4 w-4 text-[var(--accent)]" />
          <span className="mono text-[11px] font-semibold tracking-[.2em] text-white">{step.t.toUpperCase()}</span>
          <span className="mono ml-auto text-[10px] text-[var(--dim)]">{i + 1} / {STEPS.length}</span>
        </div>
        <p className="mono mt-2 text-[12px] leading-relaxed text-[var(--muted)]">{step.d}</p>
        <div className="mt-4 flex items-center justify-between">
          <button onClick={onDone} className="mono text-[10px] tracking-[.2em] text-[var(--dim)] hover:text-white">SKIP TOUR</button>
          <button onClick={next} className="btn btn-primary btn-sm">{i + 1 >= STEPS.length ? <>DONE <Check className="h-3.5 w-3.5" /></> : <>NEXT <ArrowRight className="h-3.5 w-3.5" /></>}</button>
        </div>
      </div>
    </div>
  );
}
