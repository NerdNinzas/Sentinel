"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronsUpDown, Search } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Option { value: string; label: string; hint?: string; icon?: React.ReactNode }

export function Select({ value, onChange, options, placeholder = "Select…", searchable = false, className }: {
  value: string; onChange: (v: string) => void; options: Option[]; placeholder?: string; searchable?: boolean; className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const current = options.find((o) => o.value === value);
  const filtered = useMemo(() => (q ? options.filter((o) => o.label.toLowerCase().includes(q.toLowerCase())) : options), [q, options]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDoc); document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onKey); };
  }, []);

  return (
    <div ref={ref} className={cn("relative", className)}>
      <button type="button" onClick={() => { setOpen(!open); setQ(""); }}
        className="input flex w-full items-center gap-2 text-left transition-colors hover:border-[var(--accent)]/60">
        {current?.icon}
        <span className={cn("flex-1 truncate", !current && "text-[var(--dim)]")}>{current?.label ?? placeholder}</span>
        {current?.hint && <span className="chip shrink-0">{current.hint}</span>}
        <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-[var(--dim)]" />
      </button>
      {open && (
        <div className="absolute z-50 mt-1 w-full border border-[var(--border-2)] bg-[var(--panel-2)] shadow-[0_16px_48px_rgba(0,0,0,.6)]">
          {searchable && (
            <div className="flex items-center gap-2 border-b border-[var(--border)] px-3 py-2">
              <Search className="h-3.5 w-3.5 text-[var(--dim)]" />
              <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter…"
                className="mono w-full bg-transparent text-[12.5px] outline-none placeholder:text-[var(--dim)]" />
            </div>
          )}
          <ul className="max-h-64 overflow-y-auto py-1">
            {filtered.length === 0 && <li className="mono px-3 py-3 text-center text-[11px] text-[var(--dim)]">NO MATCHES</li>}
            {filtered.map((o) => (
              <li key={o.value}>
                <button type="button" onClick={() => { onChange(o.value); setOpen(false); }}
                  className={cn("flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] transition-colors hover:bg-[var(--accent)]/12",
                    o.value === value && "bg-[var(--accent)]/8 text-white")}>
                  {o.icon}
                  <span className="flex-1 truncate">{o.label}</span>
                  {o.hint && <span className="chip shrink-0">{o.hint}</span>}
                  {o.value === value && <Check className="h-3.5 w-3.5 shrink-0 text-[var(--accent)]" />}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
