"use client";
import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowUpRight, Building2, Check, Loader2, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";

export default function InvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const router = useRouter();
  const [info, setInfo] = useState<{ org_name: string; invited_by: string; status: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.inviteInfo(token).then(setInfo).catch((e) => setErr(e.message)); }, [token]);

  const accept = async () => {
    const signedIn = !!localStorage.getItem("sentinel.session");
    if (!signedIn) {
      localStorage.setItem("sentinel.pendingInvite", token);
      router.push("/login");
      return;
    }
    setBusy(true);
    try { await api.acceptInvite(token); router.push("/dashboard"); }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : String(e)); setBusy(false); }
  };

  return (
    <main className="grid min-h-screen place-items-center px-6">
      <div className="w-full max-w-md text-center">
        <span className="glow-blue mx-auto mb-8 grid h-14 w-14 place-items-center bg-[var(--accent)]/12 text-[var(--accent)] ring-1 ring-[var(--accent)]/40"><Building2 className="h-7 w-7" /></span>
        {!info && !err && <div className="mono flex items-center justify-center gap-2 text-[11px] tracking-[.25em] text-[var(--muted)]"><Loader2 className="h-4 w-4 animate-spin" />LOADING INVITATION</div>}
        {err && <div className="mono text-[12px] text-[var(--red)]">{err}</div>}
        {info && (
          <>
            <div className="mono text-[10px] tracking-[.3em] text-[var(--muted)]">SENTINEL WORKSPACE INVITATION</div>
            <h1 className="display mt-3 text-4xl uppercase">Join {info.org_name}</h1>
            <p className="mono mt-4 text-[12.5px] leading-relaxed text-[var(--muted)]">
              <b className="text-white">{info.invited_by}</b> invited you to their incident-response workspace.
              You&apos;ll share war rooms, evidence and reports with the team.
            </p>
            {info.status === "accepted" ? (
              <div className="chip chip-green mx-auto mt-6"><Check />ALREADY ACCEPTED</div>
            ) : (
              <button onClick={accept} disabled={busy} className="btn btn-primary mx-auto mt-8 justify-center px-8 py-3">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldAlert className="h-4 w-4" />}ACCEPT INVITATION <ArrowUpRight />
              </button>
            )}
            <p className="mono mt-4 text-[10px] tracking-[.2em] text-[var(--dim)]">NO ACCOUNT YET? ACCEPTING TAKES YOU TO SIGN-UP FIRST.</p>
          </>
        )}
      </div>
    </main>
  );
}
