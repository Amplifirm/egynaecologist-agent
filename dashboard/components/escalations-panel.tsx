"use client";

import { useEffect, useState } from "react";
import type { Escalation } from "@/lib/supabase";
import { formatRelative } from "@/lib/format";

export function EscalationsPanel() {
  const [items, setItems] = useState<Escalation[]>([]);
  const [collapsed, setCollapsed] = useState(false);

  async function load() {
    const r = await fetch("/api/escalations?status=pending", { cache: "no-store" });
    if (!r.ok) return;
    const d = await r.json();
    setItems(d.escalations ?? []);
  }

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), 20000);
    return () => clearInterval(t);
  }, []);

  async function resolve(id: string) {
    await fetch(`/api/escalations/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "resolved" }),
    });
    void load();
  }
  async function dismiss(id: string) {
    if (!window.confirm("Dismiss this callback request without action?")) return;
    await fetch(`/api/escalations/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "dismissed" }),
    });
    void load();
  }

  if (items.length === 0) return null;

  return (
    <section className="mb-10 row-in">
      <div className="border-2 border-brand-pink bg-brand-pink/[0.06] p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-brand-pink animate-pulse" aria-hidden />
            <h2 className="font-display italic text-ink text-2xl leading-none">
              Callback requests waiting
            </h2>
            <span className="smcp text-[11px] tnum bg-brand-pink text-paper px-2 py-0.5">
              {items.length}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            className="smcp text-[10px] text-ink-soft hover:text-ink"
          >
            {collapsed ? "show" : "hide"}
          </button>
        </div>

        {!collapsed && (
          <ul className="divide-y divide-brand-pink/30">
            {items.map((e) => (
              <li key={e.id} className="py-3 grid grid-cols-[auto_1fr_auto_auto] gap-x-4 items-center">
                <span className={`smcp text-[10px] px-2 py-1 ${e.during_hours ? "bg-amber/20 text-amber" : "bg-brand-pink text-paper"}`}>
                  {e.during_hours ? "in-hours" : "out-of-hours"}
                </span>
                <div className="flex flex-col">
                  <span className="font-display italic text-base text-ink">{e.reason}</span>
                  <span className="text-[12px] text-ink-mute mt-0.5">
                    Calling-from <span className="font-mono tnum">{e.caller_phone}</span>
                    {e.callback_phone !== e.caller_phone && (
                      <> · Callback <span className="font-mono tnum text-brand-pink font-semibold">{e.callback_phone}</span></>
                    )}
                    {" · "}{formatRelative(e.created_at)}
                  </span>
                </div>
                <a
                  href={`tel:${e.callback_phone}`}
                  className="smcp text-[11px] text-paper bg-ink hover:bg-brand-pink hover:text-paper border border-ink hover:border-brand-pink px-3 py-1.5 transition-colors"
                  title="Call back"
                >
                  call back
                </a>
                <div className="flex items-center gap-1.5">
                  <button onClick={() => resolve(e.id)} className="smcp text-[10px] text-forest border border-rule hover:border-forest hover:text-paper hover:bg-forest px-2.5 py-1.5 transition-colors">
                    mark called
                  </button>
                  <button onClick={() => dismiss(e.id)} className="smcp text-[10px] text-ink-mute border border-rule hover:border-ink hover:text-ink px-2.5 py-1.5 transition-colors">
                    dismiss
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
