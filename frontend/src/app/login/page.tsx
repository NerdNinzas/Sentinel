"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowUpRight, Loader2, Lock, Mail, ShieldAlert, UserRound } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function Login() {
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    try { if (localStorage.getItem("sentinel.session")) router.replace("/dashboard"); } catch {}
  }, [router]);

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      const res = mode === "signup" ? await api.signup(email, password, name) : await api.login(email, password);
      localStorage.setItem("sentinel.session", res.session);
      localStorage.setItem("sentinel.me", JSON.stringify({ uid: res.user.login, name: res.user.name || res.user.login, role: "incident_commander" }));
      const pending = localStorage.getItem("sentinel.pendingInvite");
      if (pending) {
        localStorage.removeItem("sentinel.pendingInvite");
        try { await api.acceptInvite(pending); } catch { /* expired/used */ }
      }
      router.push("/dashboard");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setErr(msg.replace(/^\d+\s*/, "").replace(/^\{"detail":"|"\}$/g, ""));
    } finally { setBusy(false); }
  };

  return (
    <main className="grid min-h-screen place-items-center px-6">
      <div className="w-full max-w-md">
        <div className="mb-10 flex items-center gap-3">
          <span className="glow-blue grid h-11 w-11 place-items-center bg-[var(--accent)]/12 text-[var(--accent)] ring-1 ring-[var(--accent)]/40"><ShieldAlert className="h-6 w-6" /></span>
          <div><div className="mono text-[10px] tracking-[.3em] text-[var(--muted)]">SENTINEL / BY NERDNINZAS</div><div className="display text-3xl uppercase">{mode === "signup" ? "Create Account" : "Welcome Back"}</div></div>
        </div>
        <div className="panel p-6">
          <div className="mb-6 grid grid-cols-2 gap-1 border border-[var(--border)] p-1">
            {(["signin", "signup"] as const).map((m) => (
              <button key={m} onClick={() => { setMode(m); setErr(null); }}
                className={cn("mono py-2 text-[11px] tracking-[.2em] transition-colors", mode === m ? "bg-[var(--accent)] text-black" : "text-[var(--muted)] hover:text-white")}>
                {m === "signin" ? "SIGN IN" : "SIGN UP"}
              </button>
            ))}
          </div>
          {mode === "signup" && (
            <>
              <div className="label mb-2 flex items-center gap-2"><UserRound className="h-3.5 w-3.5 text-[var(--accent)]" />YOUR NAME</div>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Vijay Singh" className="input mb-5 w-full" />
            </>
          )}
          <div className="label mb-2 flex items-center gap-2"><Mail className="h-3.5 w-3.5 text-[var(--accent)]" />EMAIL</div>
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" placeholder="you@company.com" className="input mb-5 w-full" />
          <div className="label mb-2 flex items-center gap-2"><Lock className="h-3.5 w-3.5 text-[var(--accent)]" />PASSWORD</div>
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder={mode === "signup" ? "8+ characters" : "••••••••"} className="input w-full" onKeyDown={(e) => e.key === "Enter" && submit()} />
          <button disabled={busy || !email || !password} onClick={submit} className="btn btn-primary mt-6 w-full justify-center py-3">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}{mode === "signup" ? "CREATE ACCOUNT" : "SIGN IN"} <ArrowUpRight />
          </button>
          {err && <div className="mono mt-3 text-[11px] text-[var(--red)]">{err}</div>}
        </div>
        <p className="mono mt-6 text-center text-[10px] tracking-[.2em] text-[var(--dim)]">GITHUB, SLACK & JIRA CONNECT FROM THE DASHBOARD → INTEGRATIONS</p>
      </div>
    </main>
  );
}
