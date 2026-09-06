"use client";
import { AlertOctagon, GitCommitHorizontal, GitMerge, GitBranch } from "lucide-react";
import type { Incident } from "@/lib/types";
import { cn } from "@/lib/utils";
import { GithubIcon } from "./ui";

export function RepoPanel({ inc }: { inc: Incident }) {
  const rc = inc.repo_changes ?? {};
  if (!inc.repo) return null;
  const commits = rc.commits ?? [], prs = rc.merged_prs ?? [];
  const mins = (n?: number | null) => (n == null ? "" : n < 60 ? `${n}M AGO` : `${Math.round(n / 60)}H AGO`);
  return (
    <div className="panel p-4">
      <div className="ph"><GithubIcon />Linked repo</div>
      <a href={`https://github.com/${inc.repo}`} target="_blank" rel="noreferrer" className="mono mt-2 flex items-center gap-2 text-[13px] font-semibold text-white hover:text-[var(--accent)]">
        {inc.repo}
        {rc.branch && <span className="chip"><GitBranch />{rc.branch}</span>}
      </a>
      {rc.error && <div className="mono mt-2 text-[11px] text-[var(--amber)]">{rc.error}</div>}
      {!rc.error && !commits.length && !rc.branch && <div className="mono mt-2 text-[11px] text-[var(--dim)]">FETCHING CHANGES…</div>}
      {commits.length > 0 && (
        <>
          <div className="mono mt-4 text-[9.5px] tracking-[.22em] text-[var(--dim)]">RECENT CHANGES — LAST 24H</div>
          <ul className="mt-2 space-y-1.5">
            {commits.slice(0, 6).map((c) => (
              <li key={c.sha} className={cn("border border-transparent px-2 py-1.5 text-[12px] leading-snug", c.suspect && "border-[var(--accent)]/60 bg-[var(--accent)]/8")}>
                <div className="flex items-center gap-2">
                  <GitCommitHorizontal className="h-3.5 w-3.5 shrink-0 text-[var(--dim)]" />
                  <a href={c.url ?? "#"} target="_blank" rel="noreferrer" className="mono text-[11px] text-[var(--accent)] hover:underline">{c.sha}</a>
                  <span className="mono ml-auto text-[9px] tracking-widest text-[var(--dim)]">{mins(c.minutes_before_incident)}</span>
                  {c.suspect && <span className="chip chip-blue">SUSPECT</span>}
                </div>
                <div className="mt-0.5 truncate text-[var(--text)]/85" title={c.message}>{c.message}</div>
                <div className="mono text-[10px] text-[var(--dim)]">{c.author}</div>
              </li>
            ))}
          </ul>
        </>
      )}
      {prs.length > 0 && (
        <ul className="mt-3 space-y-1">
          {prs.slice(0, 3).map((p) => (
            <li key={p.number} className="flex items-center gap-2 text-[11px]">
              <GitMerge className="h-3.5 w-3.5 shrink-0 text-[var(--purple)]" />
              <a href={p.url ?? "#"} target="_blank" rel="noreferrer" className="mono text-[var(--muted)] hover:text-white">#{p.number}</a>
              <span className="truncate text-[var(--muted)]" title={p.title}>{p.title}</span>
              {p.suspect && <span className="chip chip-blue">!</span>}
            </li>
          ))}
        </ul>
      )}
      {(rc.failed_runs?.length ?? 0) > 0 && (
        <div className="mono mt-3 flex items-center gap-1.5 text-[10.5px] text-[var(--red)]"><AlertOctagon className="h-3.5 w-3.5" />{rc.failed_runs!.length} FAILED CI RUN(S) IN WINDOW</div>
      )}
    </div>
  );
}
