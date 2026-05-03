"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Wordmark } from "@/components/wordmark";
import { DoubleRule, Hairline } from "@/components/decorative";

type HoursMode = "auto" | "open" | "closed";

export default function SettingsPage() {
  const [agentEnabled, setAgentEnabled] = useState<boolean>(true);
  const [hoursMode, setHoursMode] = useState<HoursMode>("auto");
  const [escalationPhone, setEscalationPhone] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  async function load() {
    const r = await fetch("/api/settings", { cache: "no-store" });
    if (r.ok) {
      const d = await r.json();
      const s = d.settings ?? {};
      setAgentEnabled((s.agent_enabled ?? "true") === "true");
      if (s.hours_mode) setHoursMode(s.hours_mode as HoursMode);
      if (s.escalation_phone) setEscalationPhone(s.escalation_phone);
    }
    setLoaded(true);
  }

  useEffect(() => {
    void load();
  }, []);

  async function saveOne(payload: Record<string, string>) {
    setSaving(true);
    const r = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setSaving(false);
    if (r.ok) {
      setSavedAt(Date.now());
      setTimeout(() => setSavedAt(null), 2200);
    } else {
      alert("Save failed.");
    }
  }

  async function toggleAgent(next: boolean) {
    setAgentEnabled(next); // optimistic
    await saveOne({ agent_enabled: next ? "true" : "false" });
  }

  async function saveDeveloperOverrides() {
    await saveOne({ hours_mode: hoursMode, escalation_phone: escalationPhone.trim() });
  }

  return (
    <main className="min-h-screen relative">
      <header className="px-6 sm:px-10 lg:px-16 pt-10 pb-6">
        <DoubleRule className="mb-8" />
        <div className="flex items-end justify-between flex-wrap gap-6">
          <Wordmark size="md" />
          <Link href="/admin" className="smcp text-ink-soft hover:text-ink text-[10px] underline-offset-4 hover:underline">
            ← back to ledger
          </Link>
        </div>
      </header>

      <section className="px-6 sm:px-10 lg:px-16 pb-24 max-w-3xl">
        <div className="mb-8">
          <h1 className="font-display italic text-ink text-4xl leading-tight mb-2">Reception controls</h1>
          <p className="text-ink-soft text-sm max-w-prose leading-relaxed">
            Switch Sophia on whenever you'll be away from reception — over lunch,
            during a meeting, or at the end of the day. She'll capture appointment
            requests and the team can follow up by email.
          </p>
        </div>

        {!loaded ? (
          <p className="text-ink-mute italic">Loading…</p>
        ) : (
          <>
            {/* AGENT ON/OFF — the headline toggle */}
            <div className={`border-2 ${agentEnabled ? "border-brand-green bg-brand-green/[0.05]" : "border-rule bg-paper-soft"} p-8 mb-8 transition-colors duration-300`}>
              <div className="flex items-start justify-between gap-6">
                <div>
                  <p className="smcp text-[10px] text-ink-mute mb-2">sophia status</p>
                  <h2 className="font-display italic text-ink text-3xl mb-1">
                    {agentEnabled ? "Sophia is taking calls" : "Sophia is off"}
                  </h2>
                  <p className="text-ink-soft text-sm leading-relaxed mt-2 max-w-prose">
                    {agentEnabled ? (
                      <>
                        Inbound calls to <span className="font-mono tnum">+44 7427 905690</span> will be answered
                        by Sophia. She'll capture appointment requests and either flag callbacks or transfer to a
                        colleague when needed.
                      </>
                    ) : (
                      <>
                        Calls to <span className="font-mono tnum">+44 7427 905690</span> will not be answered.
                        Switch Sophia on whenever the line needs cover.
                      </>
                    )}
                  </p>
                </div>
                <Toggle
                  checked={agentEnabled}
                  onChange={toggleAgent}
                  disabled={saving}
                />
              </div>
            </div>

            {/* DEVELOPER OVERRIDES */}
            <div className="border border-rule bg-paper-soft p-8">
              <h2 className="font-display italic text-ink text-2xl mb-1">Developer overrides</h2>
              <Hairline className="mb-5" />
              <p className="text-ink-soft text-sm leading-relaxed mb-6 max-w-prose">
                These tweak Sophia's behaviour for testing. Working hours are
                <strong> Mon–Fri 09:00–17:00</strong> London. <span className="font-display italic">Auto</span>
                derives the mode from the clock; the others force a mode regardless.
              </p>

              {/* Hours mode */}
              <div className="mb-8">
                <p className="smcp text-[11px] text-ink-mute mb-3">hours mode</p>
                <fieldset className="grid grid-cols-1 gap-3">
                  <RadioCard
                    checked={hoursMode === "auto"}
                    onClick={() => setHoursMode("auto")}
                    label="auto"
                    description="Derive from London clock. Out of hours = 'we're closed' greeting; in hours = 'receptionist away briefly'."
                  />
                  <RadioCard
                    checked={hoursMode === "open"}
                    onClick={() => setHoursMode("open")}
                    label="force open"
                    description="Treat as if it's a working weekday. Live transfers attempted on escalation."
                    accent="forest"
                  />
                  <RadioCard
                    checked={hoursMode === "closed"}
                    onClick={() => setHoursMode("closed")}
                    label="force closed"
                    description="Treat as if the office is shut. Escalations go straight to callback."
                    accent="brand-pink"
                  />
                </fieldset>
              </div>

              {/* Escalation phone */}
              <div className="mb-8">
                <p className="smcp text-[11px] text-ink-mute mb-3">escalation phone</p>
                <p className="text-ink-soft text-sm leading-relaxed mb-3 max-w-prose">
                  The number live transfers are bridged to during working hours.
                </p>
                <input
                  type="tel"
                  value={escalationPhone}
                  onChange={(e) => setEscalationPhone(e.target.value)}
                  placeholder="+447554477038"
                  className="input-line w-full max-w-md font-mono text-base tnum"
                />
              </div>

              <div className="flex items-center gap-4">
                <button
                  onClick={saveDeveloperOverrides}
                  disabled={saving}
                  className="smcp text-[11px] py-3 px-6 border border-ink bg-ink text-paper hover:bg-paper hover:text-ink transition-colors disabled:opacity-50"
                >
                  {saving ? "saving" : "save overrides"}
                </button>
                {savedAt && (
                  <span className="font-display italic text-forest text-sm">— saved.</span>
                )}
              </div>
            </div>
          </>
        )}
      </section>
    </main>
  );
}

function Toggle({ checked, onChange, disabled = false }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      disabled={disabled}
      role="switch"
      aria-checked={checked}
      className={`
        relative inline-flex items-center w-20 h-11 border-2
        transition-colors duration-300 cursor-pointer disabled:cursor-not-allowed
        ${checked ? "bg-brand-green border-brand-green" : "bg-paper-tint border-rule hover:border-ink"}
      `}
    >
      <span
        className={`
          absolute top-1/2 -translate-y-1/2 w-7 h-7 bg-paper border border-ink/20
          transition-all duration-300 shadow-sm
          ${checked ? "left-[calc(100%-32px)]" : "left-1"}
        `}
        aria-hidden
      />
      <span className="sr-only">{checked ? "Sophia is on" : "Sophia is off"}</span>
    </button>
  );
}

function RadioCard({
  checked, onClick, label, description, accent,
}: {
  checked: boolean;
  onClick: () => void;
  label: string;
  description: string;
  accent?: "forest" | "brand-pink";
}) {
  const ring = checked
    ? accent === "forest"
      ? "border-forest bg-forest/[0.04]"
      : accent === "brand-pink"
        ? "border-brand-pink bg-brand-pink/[0.05]"
        : "border-ink bg-paper-tint/40"
    : "border-rule hover:border-ink";

  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-left p-4 border transition-all duration-200 ${ring}`}
    >
      <div className="flex items-center gap-3">
        <span
          className={`inline-block w-3 h-3 rounded-full border ${checked ? (accent === "forest" ? "bg-forest border-forest" : accent === "brand-pink" ? "bg-brand-pink border-brand-pink" : "bg-ink border-ink") : "border-rule"}`}
          aria-hidden
        />
        <span className="smcp text-[12px] text-ink">{label}</span>
      </div>
      <p className="mt-2 text-[13px] text-ink-soft leading-relaxed pl-6">{description}</p>
    </button>
  );
}
