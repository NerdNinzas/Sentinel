"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import { api } from "@/lib/api";

export default function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [md, setMd] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = () => api.report(id).then((r) => setMd(r.markdown)).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <Link href={`/incident/${id}`} className="text-sm text-[var(--muted)] hover:text-white">← back to war room</Link>
        <div className="flex gap-2">
          <button onClick={load} className="rounded-md border border-[var(--border)] px-3 py-1 text-sm">Regenerate</button>
          <button onClick={() => md && navigator.clipboard.writeText(md)} className="rounded-md border border-[var(--border)] px-3 py-1 text-sm">Copy markdown</button>
        </div>
      </div>
      {err && <div className="text-[var(--red)]">{err}</div>}
      {!md && !err && <div className="text-[var(--muted)]">Generating report…</div>}
      {md && <article className="panel prose-md p-6 text-sm"><ReactMarkdown>{md}</ReactMarkdown></article>}
    </main>
  );
}
