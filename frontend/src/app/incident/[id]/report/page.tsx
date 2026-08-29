"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowLeft, Copy, FileText, Loader2, Printer, RefreshCw, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";

export default function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [md, setMd] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const load = () => { setMd(null); api.report(id).then((r) => setMd(r.markdown)).catch((e) => setErr(e.message)); };
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <Link href={`/incident/${id}`} className="btn btn-ghost"><ArrowLeft />War room</Link>
        <div className="flex items-center gap-2 text-[11px] tracking-[.2em] text-[var(--muted)]"><ShieldAlert className="h-4 w-4 text-[var(--blue)]" />SENTINEL · INCIDENT REPORT</div>
        <div className="flex gap-2">
          <button onClick={load} className="btn"><RefreshCw />Regenerate</button>
          <button onClick={() => { if (md) { navigator.clipboard.writeText(md); setCopied(true); setTimeout(() => setCopied(false), 1500); } }} className="btn"><Copy />{copied ? "Copied" : "Copy markdown"}</button>
          <button onClick={() => window.print()} className="btn"><Printer /></button>
        </div>
      </div>
      {err && <div className="text-[var(--red)]">{err}</div>}
      {!md && !err && <div className="flex items-center gap-2 text-[var(--muted)]"><Loader2 className="h-4 w-4 animate-spin" />Generating report…</div>}
      {md && <article className="panel prose-md p-7 text-sm"><div className="ph mb-2"><FileText />Post-incident report</div><ReactMarkdown remarkPlugins={[remarkGfm]}>{md}</ReactMarkdown></article>}
    </main>
  );
}
