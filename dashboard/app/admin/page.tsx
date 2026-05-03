import Link from "next/link";
import { getSupabase, type Booking } from "@/lib/supabase";
import { Ledger } from "@/components/ledger";
import { Wordmark } from "@/components/wordmark";
import { DoubleRule } from "@/components/decorative";
import { formatHeaderDate, todayLondon } from "@/lib/format";

export const dynamic = "force-dynamic";

async function fetchInitialBookings(): Promise<Booking[]> {
  const sb = getSupabase();
  // Most recent first — these are appointment requests, not booked slots.
  const { data, error } = await sb
    .from("bookings")
    .select("*")
    .order("created_at", { ascending: false });
  if (error) {
    console.error("Initial bookings fetch failed:", error);
    return [];
  }
  return (data ?? []) as Booking[];
}

async function fetchAgentEnabled(): Promise<boolean> {
  const sb = getSupabase();
  const { data } = await sb.from("app_settings").select("value").eq("key", "agent_enabled").limit(1);
  if (!data || data.length === 0) return true;
  return data[0].value === "true";
}

export default async function AdminPage() {
  const [initial, agentEnabled] = await Promise.all([
    fetchInitialBookings(),
    fetchAgentEnabled(),
  ]);
  const today = todayLondon();
  const newToday = initial.filter((b) => b.created_at.slice(0, 10) === today).length;
  const headerDate = formatHeaderDate();

  return (
    <main className="min-h-screen relative">
      {/* === Header letterhead === */}
      <header className="relative z-10 px-6 sm:px-10 lg:px-16 pt-10 pb-6">
        <DoubleRule className="mb-8" />
        <div className="flex items-start justify-between flex-wrap gap-6">
          <Wordmark size="md" />
          <div className="flex items-center gap-6">
            <Link
              href="/admin/settings"
              className={`
                inline-flex items-center gap-2.5 px-3.5 py-2 border transition-colors
                ${agentEnabled
                  ? "border-brand-green bg-brand-green/[0.07] hover:bg-brand-green/[0.12]"
                  : "border-rule bg-paper-soft hover:border-ink"}
              `}
              title="Manage in settings"
            >
              <span className={`relative flex w-2.5 h-2.5`} aria-hidden>
                <span className={`absolute inline-flex h-full w-full rounded-full ${agentEnabled ? "bg-brand-green animate-ping opacity-60" : "bg-ink-mute"}`} />
                <span className={`relative inline-flex w-2.5 h-2.5 rounded-full ${agentEnabled ? "bg-brand-green" : "bg-ink-mute"}`} />
              </span>
              <span className="smcp text-[10px] text-ink-soft">sophia</span>
              <span className={`font-display italic text-sm ${agentEnabled ? "text-ink" : "text-ink-mute"}`}>
                {agentEnabled ? "taking calls" : "off"}
              </span>
            </Link>

            <div className="flex flex-col items-end text-right">
              <span className="smcp text-ink-mute text-[10px]">today</span>
              <span className="font-display italic text-ink-soft text-lg leading-tight mt-0.5">
                {headerDate}
              </span>
              <span className="smcp text-ink-mute text-[10px] mt-2">
                {newToday > 0 ? (
                  <>
                    <span className="text-claret font-semibold tnum">{newToday}</span> new today
                  </>
                ) : (
                  "no new requests yet"
                )}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* === Unified Ledger === */}
      <section className="relative z-10 px-6 sm:px-10 lg:px-16 pb-24">
        <Ledger initial={initial} />
      </section>

      {/* === Footer === */}
      <footer className="relative z-10 px-6 sm:px-10 lg:px-16 pb-10">
        <DoubleRule className="mb-4" />
        <div className="flex items-center justify-between text-[10px] smcp text-ink-mute">
          <span>egynaecologist · interim ledger · supabase-backed</span>
          <div className="flex items-center gap-5">
            <Link href="/admin/settings" className="hover:text-ink transition-colors">
              developer settings
            </Link>
            <form action="/api/logout" method="POST">
              <button type="submit" className="hover:text-ink transition-colors">
                sign out
              </button>
            </form>
          </div>
        </div>
      </footer>
    </main>
  );
}
