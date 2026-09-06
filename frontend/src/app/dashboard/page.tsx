"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowUpRight, BadgeCheck, Bell, Building2, Check, Copy, CreditCard, Crown, DoorOpen, Gauge, Link2,
  Loader2, LogOut, Mail, Mic, Plug, Radio, Send, Settings2, ShieldAlert, Siren, Sparkles, User2, Users, X, Zap,
} from "lucide-react";
import { api, API_BASE, session, type AuthUser, type OrgOverview, type RepoListing, type RoomEntry } from "@/lib/api";
import type { Role } from "@/lib/types";
import { cn, roleLabel } from "@/lib/utils";
import { GithubIcon, JiraIcon, SlackIcon, Avatar } from "@/components/ui";
import { Select } from "@/components/Select";
import { OnboardingModal, TourOverlay } from "@/components/onboarding";

const ROLES: Role[] = ["incident_commander", "sre", "backend", "frontend", "database", "security", "support", "product", "business", "observer"];
type View = "overview" | "rooms" | "integrations" | "team" | "profile" | "settings";

const NAV: Array<{ id: View; label: string; Icon: React.ComponentType<{ className?: string }> }> = [
  { id: "overview", label: "Overview", Icon: Gauge },
  { id: "rooms", label: "War Rooms", Icon: Siren },
  { id: "integrations", label: "Integrations", Icon: Plug },
  { id: "team", label: "Team", Icon: Users },
  { id: "profile", label: "Profile", Icon: User2 },
  { id: "settings", label: "Settings", Icon: Settings2 },
];

function trialDaysLeft(): number {
  try {
    let t = localStorage.getItem("sentinel.trialStart");
    if (!t) { t = String(Date.now()); localStorage.setItem("sentinel.trialStart", t); }
    return Math.max(0, 14 - Math.floor((Date.now() - Number(t)) / 86400000));
  } catch { return 14; }
}

export default function Dashboard() {
  const router = useRouter();
  const [view, setView] = useState<View>("overview");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [org, setOrg] = useState<OrgOverview | null>(null);
  const [rooms, setRooms] = useState<RoomEntry[]>([]);
  const [active, setActive] = useState<Awaited<ReturnType<typeof api.listIncidents>>>([]);
  const [repos, setRepos] = useState<RepoListing[]>([]);
  const [title, setTitle] = useState("Payment API Outage");
  const [severity, setSeverity] = useState("SEV-1");
  const [repo, setRepo] = useState("");
  const [role, setRole] = useState<Role>("incident_commander");
  const [busy, setBusy] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showTour, setShowTour] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const days = useMemo(() => (typeof window === "undefined" ? 14 : trialDaysLeft()), []);

  const loadRepos = useCallback(() => {
    api.repos().then((r) => { setRepos(r); if (r[0]) setRepo((cur) => cur || r[0].full_name); }).catch(() => {});
  }, []);
  const loadOrg = useCallback(() => { api.orgOverview().then(setOrg).catch(() => {}); }, []);

  useEffect(() => {
    const h = window.location.hash.replace("#", "") as View;
    if (NAV.some((n) => n.id === h)) setView(h);
    try { const me = JSON.parse(localStorage.getItem("sentinel.me") || "null"); if (me?.role) setRole(me.role); } catch {}
    api.me().then((u) => {
      setUser(u);
      setNotice(u.org_notice ?? null);
      if (!u.onboarded) setShowOnboarding(true);
      else if (!localStorage.getItem("sentinel.tourDone")) setShowTour(true);
      if (u.github_connected) loadRepos();
      if (u.org_id) loadOrg();
    }).catch(() => router.replace("/login"));
    api.myRooms().then(setRooms).catch(() => {});
    api.listIncidents().then((l) => setActive(l.filter((i) => i.status !== "resolved"))).catch(() => {});
  }, [router, loadRepos, loadOrg]);

  const nav = (v: View) => { setView(v); window.location.hash = v; };
  const join = async (id: string) => {
    setBusy(true);
    try {
      localStorage.setItem("sentinel.me", JSON.stringify({ uid: user?.login, name: user?.name || user?.login, role }));
      await api.join(id, user!.login, user!.name || user!.login, role);
      router.push(`/incident/${id}`);
    } finally { setBusy(false); }
  };
  const declare = async () => {
    setBusy(true);
    try { const inc = await api.createIncident(title, severity, repo.trim()); await join(inc.id); }
    catch (e: unknown) { setBusy(false); alert(e instanceof Error ? e.message : String(e)); }
  };
  const signOut = () => { localStorage.removeItem("sentinel.session"); router.push("/"); };
  const dismissNotice = () => { setNotice(null); api.ackNotice().catch(() => {}); };

  if (!user) return <div className="grid h-screen place-items-center"><span className="mono flex items-center gap-2 text-[11px] tracking-[.25em] text-[var(--muted)]"><Loader2 className="h-4 w-4 animate-spin" />AUTHENTICATING</span></div>;

  const created = rooms.filter((r) => r.kind === "created").length;
  const liveSev1 = active.filter((i) => i.severity === "SEV-1").length;

  return (
    <div className="flex min-h-screen">
      {showOnboarding && <OnboardingModal user={user} onDone={(u) => { setUser(u); setShowOnboarding(false); if (u.org_id) loadOrg(); if (!localStorage.getItem("sentinel.tourDone")) setShowTour(true); }} />}
      {showTour && !showOnboarding && <TourOverlay setView={(v) => nav(v as View)} onDone={() => { setShowTour(false); nav("overview"); localStorage.setItem("sentinel.tourDone", "1"); }} />}

      {/* ============ SIDEBAR ============ */}
      <aside className="fixed inset-y-0 left-0 z-40 flex w-[236px] flex-col border-r border-[var(--border)] bg-[var(--bg-2)]">
        <a href="/" className="flex items-center gap-3 border-b border-[var(--border)] px-5 py-4">
          <span className="grid h-9 w-9 place-items-center bg-[var(--accent)]/12 text-[var(--accent)] ring-1 ring-[var(--accent)]/40"><ShieldAlert className="h-5 w-5" /></span>
          <span><span className="mono block text-[11px] font-semibold tracking-[.24em]">SENTINEL</span><span className="mono block text-[7.5px] tracking-[.3em] text-[var(--dim)]">BY NERDNINZAS</span></span>
        </a>
        <div className="flex items-center gap-2 border-b border-[var(--border)] px-5 py-3">
          <Building2 className="h-3.5 w-3.5 shrink-0 text-[var(--accent)]" />
          <span className="mono truncate text-[10.5px] font-semibold tracking-[.14em] text-white">{user.org_name?.toUpperCase() ?? "PERSONAL WORKSPACE"}</span>
          {user.org_role === "owner" && <Crown className="h-3 w-3 shrink-0 text-[var(--amber)]" />}
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV.map(({ id, label, Icon }) => (
            <button key={id} onClick={() => nav(id)}
              className={cn("mono flex w-full items-center gap-3 px-3 py-2.5 text-[11px] tracking-[.18em] transition-colors",
                view === id ? "border-l-2 border-[var(--accent)] bg-[var(--accent)]/8 text-white" : "border-l-2 border-transparent text-[var(--muted)] hover:bg-white/[.03] hover:text-white")}>
              <Icon className={cn("h-4 w-4", view === id && "text-[var(--accent)]")} />{label.toUpperCase()}
              {id === "team" && (org?.members.length ?? 0) > 1 && <span className="mono ml-auto text-[9px] text-[var(--dim)]">{org?.members.length}</span>}
            </button>
          ))}
        </nav>
        <div className="border-t border-[var(--border)] px-4 py-3">
          <div className="mono mb-2 flex items-center justify-between text-[9px] tracking-[.2em] text-[var(--dim)]"><span>PRO TRIAL</span><span className="text-[var(--amber)]">{days}D LEFT</span></div>
          <div className="h-1 bg-[var(--panel-3)]"><div className="h-1 bg-[var(--amber)]" style={{ width: `${(days / 14) * 100}%` }} /></div>
        </div>
        <div className="flex items-center gap-2.5 border-t border-[var(--border)] px-4 py-4">
          {user.avatar_url ? <img src={user.avatar_url} alt="" className="h-8 w-8 border border-[var(--border-2)]" /> : <Avatar uid={user.login} name={user.name || user.login} size={32} />}
          <div className="min-w-0 flex-1"><div className="truncate text-[13px] font-medium">{user.name || user.login}</div><div className="mono truncate text-[9px] tracking-wider text-[var(--dim)]">{user.email}</div></div>
          <button onClick={signOut} title="Sign out" className="text-[var(--dim)] hover:text-[var(--red)]"><LogOut className="h-4 w-4" /></button>
        </div>
      </aside>

      {/* ============ CONTENT ============ */}
      <main className="ml-[236px] flex-1 px-10 py-9">
        {notice && (
          <div className="mb-6 flex items-center gap-3 border border-[var(--green)]/50 bg-[var(--green)]/8 px-4 py-3">
            <BadgeCheck className="h-4 w-4 shrink-0 text-[var(--green)]" />
            <span className="mono flex-1 text-[12px] tracking-wide text-[var(--text)]">{notice.toUpperCase()} 🎉</span>
            <button onClick={dismissNotice} className="text-[var(--dim)] hover:text-white"><X className="h-4 w-4" /></button>
          </div>
        )}

        {view === "overview" && (
          <section>
            <PageHead label="00 / OVERVIEW" title={`Welcome back, ${(user.name || user.login || "").split(" ")[0]}`} />
            <div className="mt-8 grid grid-cols-2 gap-4 xl:grid-cols-4">
              <Stat Icon={Siren} label="Live incidents" value={String(active.length)} tone={active.length ? "red" : "green"} />
              <Stat Icon={Zap} label="SEV-1 burning" value={String(liveSev1)} tone={liveSev1 ? "red" : "green"} />
              <Stat Icon={DoorOpen} label="Rooms joined" value={String(rooms.length)} tone="neutral" />
              <Stat Icon={Users} label="Team members" value={String(org?.members.length ?? 1)} tone="neutral" />
            </div>
            <div className="mt-10 grid grid-cols-1 gap-8 xl:grid-cols-2">
              <div>
                <div className="label label-accent mb-4">LIVE NOW</div>
                <RoomList list={active} onJoin={join} busy={busy} empty="NO LIVE INCIDENTS. QUIET IS GOOD." />
                <button onClick={() => nav("rooms")} className="btn mt-4"><Siren className="h-4 w-4" />DECLARE AN INCIDENT <ArrowUpRight /></button>
              </div>
              <div>
                <div className="label label-accent mb-4">YOUR RECENT ROOMS</div>
                <RecentRooms rooms={rooms} onJoin={join} />
              </div>
            </div>
          </section>
        )}

        {view === "rooms" && (
          <section>
            <PageHead label="01 / WAR ROOMS" title="Declare an incident" />
            <div className="panel mt-8 max-w-3xl p-6">
              <div className="label mb-3">INCIDENT</div>
              <div className="flex gap-3">
                <input value={title} onChange={(e) => setTitle(e.target.value)} className="input flex-1" />
                <Select className="w-36" value={severity} onChange={setSeverity} options={["SEV-1", "SEV-2", "SEV-3"].map((v) => ({ value: v, label: v }))} />
                <Select className="w-60" value={role} onChange={(v) => setRole(v as Role)} options={ROLES.map((r) => ({ value: r, label: roleLabel(r).toUpperCase() }))} />
              </div>
              <div className="label mb-3 mt-7 flex items-center gap-2"><GithubIcon className="h-3.5 w-3.5 text-[var(--accent)]" />LINKED REPO — COMMITS & PRS BECOME EVIDENCE</div>
              {repos.length > 0 ? (
                <Select searchable value={repo} onChange={setRepo} placeholder="Pick a repository…"
                  options={[...repos.map((r) => ({ value: r.full_name, label: r.full_name, hint: r.private ? "PRIVATE" : "PUBLIC", icon: <GithubIcon className="h-3.5 w-3.5 text-[var(--muted)]" /> })), { value: "", label: "— NO REPO —" }]} />
              ) : (
                <div className="flex gap-3">
                  <input value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="owner/repo" className="input flex-1" />
                  {!user.github_connected && <button onClick={() => nav("integrations")} className="btn btn-sm shrink-0"><GithubIcon className="h-3.5 w-3.5" />CONNECT GITHUB</button>}
                </div>
              )}
              <button disabled={busy} onClick={declare} className="btn btn-danger mt-6 w-full justify-center py-3.5">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Siren className="h-4 w-4" />}DECLARE {severity} & OPEN WAR ROOM <ArrowUpRight /></button>
            </div>
            <div className="label label-accent mb-4 mt-12">LIVE ROOMS — {active.length}</div>
            <div className="max-w-3xl"><RoomList list={active} onJoin={join} busy={busy} empty="NO LIVE INCIDENTS. DECLARE ONE ABOVE." /></div>
          </section>
        )}

        {view === "integrations" && <IntegrationsView user={user} onUser={(u) => { setUser(u); if (u.github_connected) loadRepos(); }} />}
        {view === "team" && <TeamView user={user} org={org} refresh={loadOrg} goOnboard={() => setShowOnboarding(true)} />}

        {view === "profile" && (
          <section>
            <PageHead label="04 / PROFILE" title="Operator identity" />
            <div className="panel mt-8 max-w-2xl p-6">
              <div className="flex items-center gap-5">
                {user.avatar_url ? <img src={user.avatar_url} alt="" className="h-20 w-20 border border-[var(--border-2)]" /> : <Avatar uid={user.login} name={user.name || user.login} size={80} />}
                <div>
                  <div className="text-2xl font-medium">{user.name || user.login}</div>
                  <div className="mono mt-1 text-[11px] tracking-wider text-[var(--muted)]">{user.email}</div>
                  <div className="mt-3 flex gap-2">
                    <span className="chip chip-green"><Check className="h-3 w-3" />{user.account_type === "organization" ? "ORGANIZATION" : "PERSONAL"}</span>
                    {user.org_name && <span className="chip chip-blue"><Building2 className="h-3 w-3" />{user.org_name.toUpperCase()} · {user.org_role?.toUpperCase()}</span>}
                    {user.github_connected && <span className="chip"><GithubIcon className="h-3 w-3" />@{user.github_login}</span>}
                  </div>
                </div>
              </div>
              <div className="label mb-3 mt-8">DEFAULT WAR-ROOM ROLE</div>
              <Select value={role} onChange={(v) => { setRole(v as Role); localStorage.setItem("sentinel.me", JSON.stringify({ uid: user.login, name: user.name || user.login, role: v })); }}
                options={ROLES.map((r) => ({ value: r, label: roleLabel(r).toUpperCase() }))} />
              <div className="mt-8 grid grid-cols-3 gap-3">
                <MiniStat label="ROOMS COMMANDED" value={String(created)} />
                <MiniStat label="ROOMS JOINED" value={String(rooms.length)} />
                <MiniStat label="TEAM SIZE" value={String(org?.members.length ?? 1)} />
              </div>
            </div>
          </section>
        )}

        {view === "settings" && (
          <section>
            <PageHead label="05 / SETTINGS" title="Plan & preferences" />
            <div className="mt-8 grid max-w-3xl grid-cols-1 gap-5 md:grid-cols-2">
              <div className="panel p-5">
                <div className="ph"><CreditCard />Plan</div>
                <div className="mt-4 flex items-baseline gap-3"><span className="display text-3xl uppercase">Pro Trial</span><span className="chip chip-amber">{days} DAYS LEFT</span></div>
                <div className="mt-3 h-1.5 bg-[var(--panel-3)]"><div className="h-1.5 bg-[var(--amber)] transition-all" style={{ width: `${(days / 14) * 100}%` }} /></div>
                <p className="mono mt-3 text-[10.5px] leading-relaxed tracking-wider text-[var(--muted)]">UNLIMITED ROOMS · VOICE AGENT · GITHUB EVIDENCE · AI EXTRACTION · TEAM WORKSPACE</p>
                <button className="btn btn-primary mt-5 w-full justify-center"><Sparkles className="h-4 w-4" />UPGRADE TO TEAM</button>
              </div>
              <div className="space-y-5">
                <SettingRow Icon={Mic} title="Voice" desc="Agora ASR language" control={<span className="chip">EN-US</span>} />
                <SettingRow Icon={Radio} title="AI model" desc="Extraction & interventions" control={<span className="chip chip-blue">GEMINI 2.5 FLASH</span>} />
                <SettingRow Icon={Bell} title="Notifications" desc="Approval requests & follow-ups" control={<span className="chip chip-green">IN-ROOM</span>} />
                <SettingRow Icon={ShieldAlert} title="Human gate" desc="Approval required for production actions" control={<span className="chip chip-green">ALWAYS ON</span>} />
              </div>
            </div>
            <button onClick={signOut} className="btn mt-8 border-[var(--red)]/60 text-[var(--red)]"><LogOut className="h-4 w-4" />SIGN OUT</button>
          </section>
        )}
      </main>
    </div>
  );
}

/* ================= TEAM ================= */
function TeamView({ user, org, refresh, goOnboard }: { user: AuthUser; org: OrgOverview | null; refresh: () => void; goOnboard: () => void }) {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [sent, setSent] = useState<string | null>(null);

  if (!user.org_id) {
    return (
      <section>
        <PageHead label="03 / TEAM" title="No workspace yet" />
        <div className="sigcard mt-8 max-w-xl !p-8 text-center">
          <Building2 className="mx-auto h-8 w-8 text-[var(--accent)]" />
          <p className="mono mt-4 text-[12px] leading-relaxed text-[var(--muted)]">You&apos;re on a personal account. Create an organization workspace to invite teammates into shared war rooms.</p>
          <button onClick={goOnboard} className="btn btn-primary mt-6 justify-center">CREATE ORGANIZATION <ArrowUpRight /></button>
        </div>
      </section>
    );
  }

  const invite = async (withEmail: boolean) => {
    setBusy(true); setSent(null);
    try {
      const res = await api.createInvite(withEmail ? email : undefined);
      setLink(res.link);
      if (withEmail) { setSent(res.emailed ? `Invitation emailed to ${email}` : `Email not configured — share the link below with ${email}`); setEmail(""); }
      refresh();
    } catch (e: unknown) { alert(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };

  return (
    <section>
      <PageHead label="03 / TEAM" title={org?.org?.name ?? "Team"} />
      {org?.org?.address && <div className="mono mt-2 text-[11px] tracking-wider text-[var(--dim)]">{org.org.address.toUpperCase()}</div>}
      <div className="mt-10 grid grid-cols-1 gap-10 lg:grid-cols-2">
        <div>
          <div className="label label-accent mb-4">MEMBERS — {org?.members.length ?? 0}</div>
          <ul className="space-y-2">
            {(org?.members ?? []).map((m) => (
              <li key={String(m.id)} className="flex items-center gap-3 border border-[var(--border)] bg-[var(--panel)] px-4 py-3">
                {m.avatar_url ? <img src={m.avatar_url} alt="" className="h-9 w-9 border border-[var(--border-2)]" /> : <Avatar uid={m.login} name={m.name || m.login} size={36} />}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-[14px] font-medium">{m.name || m.login}{String(m.id) === String(user.id) && <span className="chip">YOU</span>}</div>
                  <div className="mono text-[10px] tracking-wider text-[var(--dim)]">{m.email}</div>
                </div>
                <span className={cn("chip", m.org_role === "owner" ? "chip-amber" : "chip-blue")}>{m.org_role === "owner" && <Crown className="h-3 w-3" />}{(m.org_role ?? "member").toUpperCase()}</span>
              </li>
            ))}
          </ul>
          {(org?.invites.filter((i) => i.status === "pending").length ?? 0) > 0 && (
            <>
              <div className="label mb-3 mt-8">PENDING INVITES</div>
              <ul className="space-y-1.5">
                {org!.invites.filter((i) => i.status === "pending").map((i) => (
                  <li key={i.token} className="mono flex items-center gap-2 border border-dashed border-[var(--border-2)] px-3 py-2 text-[11px] text-[var(--muted)]">
                    <Mail className="h-3.5 w-3.5 text-[var(--amber)]" />{i.email ?? "invite link"}<span className="chip chip-amber ml-auto">PENDING</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
        <div>
          <div className="label label-accent mb-4">INVITE TEAMMATES</div>
          <div className="panel p-5">
            <div className="label mb-2 flex items-center gap-2"><Send className="h-3.5 w-3.5 text-[var(--accent)]" />BY EMAIL</div>
            <div className="flex gap-2">
              <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" placeholder="teammate@company.com" className="input flex-1" />
              <button disabled={!email.includes("@") || busy} onClick={() => invite(true)} className="btn btn-primary shrink-0">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}SEND</button>
            </div>
            {sent && <div className="mono mt-2 text-[10.5px] text-[var(--green)]">{sent}</div>}
            <div className="label mb-2 mt-7 flex items-center gap-2"><Link2 className="h-3.5 w-3.5 text-[var(--accent)]" />OR SHARE AN INVITE LINK</div>
            {link ? (
              <div className="flex gap-2">
                <input readOnly value={link} className="input mono flex-1 text-[11px]" />
                <button onClick={() => { navigator.clipboard.writeText(link); setCopied(true); setTimeout(() => setCopied(false), 1500); }} className="btn shrink-0">{copied ? <Check className="h-4 w-4 text-[var(--green)]" /> : <Copy className="h-4 w-4" />}{copied ? "COPIED" : "COPY"}</button>
              </div>
            ) : (
              <button disabled={busy} onClick={() => invite(false)} className="btn w-full justify-center"><Link2 className="h-4 w-4" />GENERATE INVITE LINK</button>
            )}
            <p className="mono mt-4 text-[10px] leading-relaxed tracking-wider text-[var(--dim)]">ANYONE WITH THE LINK CAN JOIN {org?.org?.name?.toUpperCase()}. THEY&apos;LL SIGN UP (OR IN) AND LAND IN THIS WORKSPACE.</p>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ================= INTEGRATIONS ================= */
function IntegrationsView({ user, onUser }: { user: AuthUser; onUser: (u: AuthUser) => void }) {
  const [pat, setPat] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const connect = async () => {
    setBusy(true); setErr(null);
    try { onUser(await api.connectGithub(pat)); setPat(""); }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };

  return (
    <section>
      <PageHead label="02 / INTEGRATIONS" title="Connect your stack" />
      <div className="mt-8 grid max-w-4xl grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
        {/* GitHub */}
        <div className="sigcard flex flex-col !p-6">
          <div className="flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center bg-white/8" style={{ boxShadow: "inset 0 0 0 1px #ffffff33" }}><GithubIcon className="h-5 w-5" /></span>
            <div><div className="text-xl font-medium text-white">GitHub</div>
              {user.github_connected ? <span className="chip chip-green mt-1"><Check className="h-3 w-3" />@{user.github_login}</span> : <span className="chip chip-amber mt-1">NOT CONNECTED</span>}
            </div>
          </div>
          <p className="mono mt-4 flex-1 text-[11.5px] leading-relaxed text-[var(--muted)]">Your repos become incident evidence — recent commits and PRs are pulled into the war room and correlated with hypotheses.</p>
          {user.github_connected ? (
            <button onClick={async () => onUser(await api.disconnectGithub())} className="btn mt-5 w-full justify-center border-[var(--red)]/50 text-[var(--red)]">DISCONNECT</button>
          ) : (
            <div className="mt-5 space-y-2">
              <input value={pat} onChange={(e) => setPat(e.target.value)} type="password" placeholder="ghp_… classic token" className="input w-full" />
              <button disabled={!pat.trim() || busy} onClick={connect} className="btn btn-primary w-full justify-center">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <GithubIcon className="h-4 w-4" />}CONNECT GITHUB</button>
              <a href={`${API_BASE}/api/auth/github/login?session=${session() ?? ""}`} className="btn w-full justify-center">SIGN IN WITH GITHUB <ArrowUpRight /></a>
              <a href="https://github.com/settings/tokens/new?scopes=repo,read:user&description=Sentinel" target="_blank" rel="noreferrer" className="mono block text-center text-[9.5px] tracking-[.15em] text-[var(--dim)] hover:text-white">CREATE A CLASSIC TOKEN ↗</a>
              {err && <div className="mono text-[10.5px] text-[var(--red)]">{err}</div>}
            </div>
          )}
        </div>
        {/* Slack */}
        <IntegrationCard name="Slack" Icon={SlackIcon} tile="#1a1d21" ring="#E01E5A"
          blurb="Incident channel updates, status broadcasts, and the final report — posted where the team already lives."
          open={open === "slack"} onConnect={() => setOpen(open === "slack" ? null : "slack")}
          detail={<>Create a Slack app → scopes <code className="mono">chat:write</code>, <code className="mono">channels:read</code> → install → paste the bot token in <code className="mono">backend/.env</code> as <code className="mono">SLACK_BOT_TOKEN</code>.</>} />
        {/* Jira */}
        <IntegrationCard name="Jira" Icon={JiraIcon} tile="#0b1a33" ring="#2684FF"
          blurb="Investigation tasks and post-incident follow-ups filed automatically, with owners carried over from the room."
          open={open === "jira"} onConnect={() => setOpen(open === "jira" ? null : "jira")}
          detail={<>Atlassian site URL + email + API token (id.atlassian.com) in <code className="mono">backend/.env</code> as <code className="mono">JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN</code>.</>} />
      </div>
    </section>
  );
}

/* ================= shared pieces ================= */
function PageHead({ label, title }: { label: string; title: string }) {
  return (<div><div className="label label-accent">{label}</div><h1 className="display mt-2 text-5xl uppercase">{title}</h1></div>);
}

function Stat({ Icon, label, value, tone }: { Icon: React.ComponentType<{ className?: string }>; label: string; value: string; tone: "red" | "green" | "neutral" }) {
  const c = tone === "red" ? "var(--red)" : tone === "green" ? "var(--green)" : "var(--text)";
  return (
    <div className="sigcard !p-5">
      <div className="mono flex items-center justify-between text-[9px] tracking-[.22em] text-[var(--dim)]"><span>{label.toUpperCase()}</span><Icon className="h-4 w-4" /></div>
      <div className="display mt-3 text-5xl" style={{ color: c }}>{value}</div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return <div className="border border-[var(--border)] bg-[var(--panel)] p-3 text-center"><div className="display text-2xl">{value}</div><div className="mono mt-1 text-[8.5px] tracking-[.2em] text-[var(--dim)]">{label}</div></div>;
}

function RoomList({ list, onJoin, busy, empty }: { list: Array<{ id: string; title: string; severity: string; status: string; counts: Record<string, number> }>; onJoin: (id: string) => void; busy: boolean; empty: string }) {
  if (list.length === 0) return <div className="mono border border-[var(--border)] p-6 text-center text-[10px] tracking-[.2em] text-[var(--dim)]">{empty}</div>;
  return (
    <ul className="space-y-3">
      {list.map((i) => (
        <li key={i.id} className="sigcard flex items-center gap-4 !py-4">
          <span className={cn("mono px-2 py-1 text-[10px] font-bold", i.severity === "SEV-1" ? "bg-[var(--red)] text-black" : "bg-[var(--amber)] text-black")}>{i.severity}</span>
          <div className="min-w-0 flex-1"><div className="truncate font-medium text-white">{i.title}</div><div className="mono text-[9.5px] tracking-wider text-[var(--muted)]">{i.id} · {i.status.toUpperCase()} · {i.counts.facts} FACTS · {i.counts.actions} ACTIONS</div></div>
          <button disabled={busy} onClick={() => onJoin(i.id)} className="btn btn-sm"><DoorOpen className="h-3.5 w-3.5" />JOIN</button>
        </li>
      ))}
    </ul>
  );
}

function RecentRooms({ rooms, onJoin }: { rooms: RoomEntry[]; onJoin: (id: string) => void }) {
  if (rooms.length === 0) return <div className="mono border border-[var(--border)] p-6 text-center text-[10px] tracking-[.2em] text-[var(--dim)]">NOTHING YET — DECLARE YOUR FIRST INCIDENT</div>;
  return (
    <ul className="space-y-2">
      {rooms.slice(0, 8).map((r) => (
        <li key={r.incident_id} className="flex items-center gap-3 border border-[var(--border)] bg-[var(--panel)] px-3 py-2.5">
          <span className={cn("chip", r.kind === "created" ? "chip-red" : "chip-blue")}>{r.kind}</span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px]">{r.title ?? r.incident_id}</div>
            <div className="mono text-[9px] tracking-wider text-[var(--dim)]">{r.incident_id} · {(r.status ?? "archived").toUpperCase()}{r.repo ? ` · ${r.repo}` : ""}</div>
          </div>
          {r.status && <button onClick={() => onJoin(r.incident_id)} className="btn btn-sm btn-ghost"><ArrowUpRight className="h-3.5 w-3.5" /></button>}
        </li>
      ))}
    </ul>
  );
}

function IntegrationCard({ name, Icon, tile, ring, blurb, detail, open, onConnect }: {
  name: string; Icon: React.ComponentType<{ className?: string }>; tile: string; ring: string;
  blurb: string; detail: React.ReactNode; open: boolean; onConnect: () => void;
}) {
  return (
    <div className="sigcard flex flex-col !p-6">
      <div className="flex items-center gap-3">
        <span className="grid h-11 w-11 place-items-center" style={{ background: tile, boxShadow: `inset 0 0 0 1px ${ring}66` }}><Icon className="h-5 w-5" /></span>
        <div><div className="text-xl font-medium text-white">{name}</div><span className="chip chip-amber mt-1">NOT CONNECTED</span></div>
      </div>
      <p className="mono mt-4 flex-1 text-[11.5px] leading-relaxed text-[var(--muted)]">{blurb}</p>
      <button onClick={onConnect} className="btn btn-primary mt-5 w-full justify-center">CONNECT {name.toUpperCase()} <ArrowUpRight /></button>
      {open && <div className="mono mt-4 border border-[var(--amber)]/40 bg-[var(--amber)]/6 p-3 text-[10.5px] leading-relaxed text-[var(--muted)]">{detail}</div>}
    </div>
  );
}

function SettingRow({ Icon, title, desc, control }: { Icon: React.ComponentType<{ className?: string }>; title: string; desc: string; control: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 border border-[var(--border)] bg-[var(--panel)] px-4 py-3.5">
      <Icon className="h-4 w-4 shrink-0 text-[var(--accent)]" />
      <div className="flex-1"><div className="text-[13px] font-medium">{title}</div><div className="mono text-[9.5px] tracking-wider text-[var(--dim)]">{desc.toUpperCase()}</div></div>
      {control}
    </div>
  );
}
