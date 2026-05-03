"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Wordmark } from "@/components/wordmark";
import { Ornament, DoubleRule } from "@/components/decorative";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (res.ok) {
      startTransition(() => router.replace("/admin"));
    } else if (res.status === 401) {
      setError("That password isn't recognised.");
    } else {
      setError("Something went wrong. Please try again in a moment.");
    }
  }

  return (
    <main className="relative min-h-screen flex items-center justify-center px-6 py-12">
      {/* corner letterhead */}
      <div className="pointer-events-none absolute top-8 left-8 right-8 flex items-center justify-between">
        <span className="smcp text-ink-mute text-[10px]">est. mmxxv</span>
        <span className="smcp text-ink-mute text-[10px]">harley street · london</span>
      </div>

      <div className="w-full max-w-md relative z-10">
        <DoubleRule className="mb-12" />

        <div className="flex flex-col items-center text-center mb-10">
          <Wordmark size="lg" showSubtitle={false} className="items-center" />
          <p className="font-display italic text-ink-soft text-base mt-5">
            front desk &middot; bookings ledger
          </p>
        </div>

        <Ornament className="mb-10" />

        <form onSubmit={submit} className="flex flex-col gap-6">
          <div>
            <label htmlFor="password" className="smcp text-ink-mute text-[11px] block mb-2">
              attendant password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              autoFocus
              required
              minLength={4}
              className="input-line text-lg"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="······"
              aria-invalid={Boolean(error)}
              aria-describedby={error ? "login-error" : undefined}
            />
          </div>

          {error && (
            <p
              id="login-error"
              className="font-display italic text-claret text-sm text-center"
              role="alert"
            >
              &mdash; {error} &mdash;
            </p>
          )}

          <button
            type="submit"
            disabled={pending || !password}
            className="
              group mt-2 inline-flex items-center justify-center gap-3
              border border-ink py-3.5 px-6
              text-ink hover:bg-ink hover:text-paper
              disabled:opacity-40 disabled:cursor-not-allowed
              transition-colors duration-300
              smcp text-xs
            "
          >
            <span className="h-px w-4 bg-current transition-all group-hover:w-6" />
            <span>{pending ? "entering" : "enter ledger"}</span>
            <span className="h-px w-4 bg-current transition-all group-hover:w-6" />
          </button>
        </form>

        <DoubleRule className="mt-16" />

        <p className="text-center smcp text-ink-mute text-[10px] mt-4">
          authorised personnel only · all access is logged
        </p>
      </div>
    </main>
  );
}
