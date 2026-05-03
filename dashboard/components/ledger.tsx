"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react";
import type { Booking, Escalation } from "@/lib/supabase";
import { FilterBar } from "@/components/filter-bar";
import { StatusTag } from "@/components/status-tag";
import { Hairline } from "@/components/decorative";
import { formatDate, formatTime, formatRelative, todayLondon } from "@/lib/format";

type Range = "all" | "today" | "upcoming" | "past";
type Status = "all" | "pending" | "invited" | "scheduled" | "confirmed" | "cancelled" | "declined";

type FeedItem =
  | {
      kind: "booking";
      id: string;
      created_at: string;
      booking: Booking;
      // If the same call_sid produced an escalation row, this is it. Used to
      // tag the booking with "Transfer attempted, no answer".
      transfer: Escalation | null;
    }
  | {
      kind: "escalation";
      id: string;
      created_at: string;
      escalation: Escalation;
    };

const SERVICES: { code: string; name: string; price_pence: number }[] = [
  { code: "INP-STD", name: "First Consultation (In-Person)", price_pence: 27500 },
  { code: "REM-STD", name: "First Consultation Remote (Video)", price_pence: 25000 },
  { code: "INP-FU", name: "Follow-up Consultation In-Person", price_pence: 22500 },
  { code: "REM-FU", name: "Follow-up Consultation Remote", price_pence: 20000 },
  { code: "TEL-FU", name: "Follow-up Consultation Telephone", price_pence: 20000 },
  { code: "SHORT-FU", name: "Follow-up Short Call", price_pence: 12000 },
  { code: "REPEAT-RX", name: "Repeat Prescription", price_pence: 2500 },
  { code: "BDL-PCOS", name: "PCOS Care Bundle", price_pence: 91000 },
  { code: "BDL-MEN", name: "Menopause / HRT Bundle", price_pence: 89000 },
  { code: "BDL-FERT", name: "Fertility Check Bundle", price_pence: 95000 },
  { code: "BDL-WW", name: "Well Woman Care Bundle", price_pence: 85000 },
  { code: "BDL-SH", name: "Sexual Health Bundle", price_pence: 55000 },
  { code: "BDL-ENDO", name: "Endometriosis Detection Bundle", price_pence: 139000 },
  { code: "BDL-COIL", name: "Coil Fitting or Removal Bundle", price_pence: 56000 },
  { code: "BDL-BRCA", name: "BRCA Gene Testing Bundle", price_pence: 89000 },
  { code: "BDL-OVCA", name: "Ovarian Cancer Detection Bundle", price_pence: 83000 },
  { code: "BDL-HPV", name: "HPV Vaccination Bundle", price_pence: 63000 },
  { code: "BDL-MISC", name: "Recurrent Miscarriage Bundle", price_pence: 0 },
  { code: "BDL-FIB", name: "Fibroid Monitoring Bundle", price_pence: 0 },
  { code: "BDL-CS", name: "Cancer Screening Bundle", price_pence: 0 },
];

export function Ledger({ initial }: { initial: Booking[] }) {
  const [bookings, setBookings] = useState<Booking[]>(initial);
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [range, setRange] = useState<Range>("upcoming");
  const [status, setStatus] = useState<Status>("all");
  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [, startTransition] = useTransition();

  const showToast = (kind: "ok" | "err", text: string) => {
    setToast({ kind, text });
    setTimeout(() => setToast(null), 2400);
  };

  async function refresh() {
    const params = new URLSearchParams();
    if (range !== "all") params.set("range", range);
    if (status !== "all") params.set("status", status);
    if (query) params.set("q", query);
    const [bRes, eRes] = await Promise.all([
      fetch(`/api/bookings?${params.toString()}`, { cache: "no-store" }),
      fetch(`/api/escalations?status=all`, { cache: "no-store" }),
    ]);
    if (bRes.ok) {
      const d = await bRes.json();
      startTransition(() => setBookings(d.bookings ?? []));
    }
    if (eRes.ok) {
      const d = await eRes.json();
      setEscalations(d.escalations ?? []);
    }
  }

  // Track which row IDs we've already shown so the row-in fade-up doesn't replay
  // every time the list re-renders (felt laggy on every status change).
  const animatedIds = useRef<Set<string>>(new Set());

  // Pause auto-refresh while a row is open / being edited so the 15s interval
  // can't clobber an in-progress text edit.
  const pauseRefresh = openId !== null;

  useEffect(() => { void refresh(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [range, status, query]);
  useEffect(() => {
    if (pauseRefresh) return;
    const t = setInterval(() => void refresh(), 15000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range, status, query, pauseRefresh]);

  function applyOptimistic(id: string, patch: Partial<Booking>) {
    setBookings((prev) => prev.map((b) => (b.id === id ? { ...b, ...patch } : b)));
  }

  async function patchBooking(id: string, patch: Partial<Booking>) {
    const before = bookings.find((b) => b.id === id);
    applyOptimistic(id, patch);
    const res = await fetch(`/api/bookings/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!res.ok) {
      if (before) applyOptimistic(id, before);
      const err = await res.json().catch(() => ({}));
      showToast("err", err.error === "slot_taken" ? "That slot is already taken." : "Update failed.");
      return false;
    }
    const data = await res.json();
    setBookings((prev) => prev.map((b) => (b.id === id ? data.booking : b)));
    showToast("ok", "Saved.");
    return true;
  }

  async function bulkSetStatus(s: "confirmed" | "cancelled" | "pending" | "invited" | "scheduled") {
    if (selected.size === 0) return;
    const ids = Array.from(selected);
    const res = await fetch("/api/bookings/bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids, status: s }),
    });
    if (!res.ok) {
      showToast("err", "Bulk update failed.");
      return;
    }
    setSelected(new Set());
    await refresh();
    showToast("ok", `Updated ${ids.length} ${ids.length === 1 ? "entry" : "entries"}.`);
  }

  async function bulkDelete() {
    if (selected.size === 0) return;
    const ids = Array.from(selected);
    // Split selected ids by which table they belong to.
    const bookingIds = ids.filter((id) => bookings.some((b) => b.id === id));
    const escalationIds = ids.filter((id) => escalations.some((e) => e.id === id));
    if (!window.confirm(`Permanently delete ${ids.length} selected ${ids.length === 1 ? "entry" : "entries"}? This cannot be undone.`)) return;
    const results = await Promise.allSettled([
      ...bookingIds.map((id) => fetch(`/api/bookings/${id}`, { method: "DELETE" })),
      ...escalationIds.map((id) => fetch(`/api/escalations/${id}`, { method: "DELETE" })),
    ]);
    const ok = results.filter((r) => r.status === "fulfilled" && (r as PromiseFulfilledResult<Response>).value.ok).length;
    setSelected(new Set());
    await refresh();
    if (ok === ids.length) {
      showToast("ok", `Deleted ${ok}.`);
    } else {
      showToast("err", `Deleted ${ok} of ${ids.length}. Some failed.`);
    }
  }

  async function deleteEscalation(id: string) {
    if (!window.confirm("Delete this entry permanently? This cannot be undone.")) return;
    const res = await fetch(`/api/escalations/${id}`, { method: "DELETE" });
    if (!res.ok) {
      showToast("err", "Delete failed.");
      return;
    }
    setEscalations((prev) => prev.filter((e) => e.id !== id));
    showToast("ok", "Deleted.");
  }

  async function markCancelled(id: string) {
    await patchBooking(id, { status: "cancelled" });
  }

  async function deleteBooking(id: string) {
    if (!window.confirm("Delete this booking permanently? This cannot be undone.")) return;
    const res = await fetch(`/api/bookings/${id}`, { method: "DELETE" });
    if (!res.ok) {
      showToast("err", "Delete failed.");
      return;
    }
    setBookings((prev) => prev.filter((b) => b.id !== id));
    showToast("ok", "Deleted.");
  }

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAllVisible() {
    // Collect every selectable id across bookings AND standalone escalation rows
    // so the header checkbox really does "select everything visible".
    const allIds: string[] = [];
    for (const item of feed) {
      if (item.kind === "booking") allIds.push(item.booking.id);
      else allIds.push(item.escalation.id);
    }
    if (selected.size === allIds.length && allIds.length > 0) setSelected(new Set());
    else setSelected(new Set(allIds));
  }

  function exportCsvUrl() {
    const params = new URLSearchParams();
    if (range !== "all") params.set("range", range);
    if (status !== "all") params.set("status", status);
    return `/api/bookings/export?${params.toString()}`;
  }

  const today = todayLondon();

  // Build a unified feed:
  //   - Each booking is shown, possibly tagged with the linked transfer attempt.
  //   - Escalations that have NO matching booking are shown as their own row
  //     (i.e. successful transfers, or callbacks where no details were collected).
  // We link a booking to an escalation by call_sid.
  const feed = useMemo(() => {
    const escByCallSid = new Map<string, Escalation>();
    for (const e of escalations) {
      if (e.call_sid) escByCallSid.set(e.call_sid, e);
    }
    const items: FeedItem[] = bookings.map((b) => ({
      kind: "booking" as const,
      created_at: b.created_at,
      id: `b:${b.id}`,
      booking: b,
      // If the same call_sid produced an escalation row too, that's the
      // "in-hours, transfer no answer → request taken" scenario.
      transfer: b.call_sid ? escByCallSid.get(b.call_sid) ?? null : null,
    }));
    const bookedSids = new Set(bookings.map((b) => b.call_sid).filter(Boolean) as string[]);
    for (const e of escalations) {
      if (e.call_sid && bookedSids.has(e.call_sid)) continue; // already shown via booking
      items.push({
        kind: "escalation" as const,
        created_at: e.created_at,
        id: `e:${e.id}`,
        escalation: e,
      });
    }
    items.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
    return items;
  }, [bookings, escalations]);

  // Total selectable rows = bookings + standalone escalations (matches selectAllVisible).
  const totalSelectable = feed.length;
  const allSelected = totalSelectable > 0 && selected.size === totalSelectable;

  return (
    <div>
      <FilterBar
        range={range} status={status} query={query}
        onRange={setRange} onStatus={setStatus} onQuery={setQuery}
        count={feed.length}
        exportHref={exportCsvUrl()}
      />

      {/* Bulk action bar — appears when rows are selected */}
      {selected.size > 0 && (
        <div className="row-in flex items-center justify-between bg-ink text-paper px-4 py-3 mb-4">
          <span className="smcp text-[11px]">
            <span className="tnum font-semibold">{selected.size}</span> selected
          </span>
          <div className="flex items-center gap-2 flex-wrap">
            <BulkBtn onClick={() => bulkSetStatus("invited")}>sent invite</BulkBtn>
            <BulkBtn onClick={() => bulkSetStatus("scheduled")}>booked in meddbase</BulkBtn>
            <BulkBtn onClick={() => bulkSetStatus("pending")}>revert to pending</BulkBtn>
            <BulkBtn onClick={() => bulkSetStatus("cancelled")} accent>cancel</BulkBtn>
            <BulkBtn onClick={() => void bulkDelete()} accent>delete</BulkBtn>
            <button onClick={() => setSelected(new Set())} className="smcp text-[10px] text-paper/70 hover:text-paper ml-2">
              clear selection
            </button>
          </div>
        </div>
      )}

      {/* Column heads */}
      <div className="grid grid-cols-[28px_1.3fr_1.7fr_1.8fr_1.8fr_0.7fr_28px] gap-x-4 px-2 py-3 smcp text-ink-mute text-[10px] border-b border-rule items-center">
        <button
          type="button"
          onClick={selectAllVisible}
          className="flex items-center justify-center"
          aria-label={allSelected ? "Deselect all" : "Select all"}
        >
          <Box checked={allSelected} indeterminate={selected.size > 0 && !allSelected} />
        </button>
        <span>reference</span>
        <span>patient</span>
        <span>service</span>
        <span>preferred ranges</span>
        <span>status</span>
        <span aria-hidden />
      </div>

      {feed.length === 0 ? (
        <EmptyState />
      ) : (
        <ul>
          {feed.map((item, i) => {
            const firstSeen = !animatedIds.current.has(item.id);
            if (firstSeen) animatedIds.current.add(item.id);
            const cls = firstSeen ? "row-in border-b border-rule-soft" : "border-b border-rule-soft";
            const style = firstSeen ? { animationDelay: `${Math.min(i * 18, 180)}ms` } : undefined;

            if (item.kind === "booking") {
              return (
                <li key={item.id} className={cls} style={style}>
                  <Row
                    booking={item.booking}
                    transfer={item.transfer}
                    isToday={item.booking.appointment_date === today || (item.booking.appointment_date == null && item.booking.created_at.slice(0, 10) === today)}
                    open={openId === item.booking.id}
                    selected={selected.has(item.booking.id)}
                    onSelect={() => toggleSelected(item.booking.id)}
                    onToggle={() => setOpenId(openId === item.booking.id ? null : item.booking.id)}
                    onPatch={(patch) => patchBooking(item.booking.id, patch)}
                    onCancel={() => markCancelled(item.booking.id)}
                    onDelete={() => deleteBooking(item.booking.id)}
                    showToast={showToast}
                  />
                </li>
              );
            }
            return (
              <li key={item.id} className={cls} style={style}>
                <EscalationRow
                  escalation={item.escalation}
                  selected={selected.has(item.escalation.id)}
                  onSelect={() => toggleSelected(item.escalation.id)}
                  onResolve={async () => {
                    await fetch(`/api/escalations/${item.escalation.id}`, {
                      method: "PATCH",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ status: "resolved" }),
                    });
                    void refresh();
                  }}
                  onDelete={() => deleteEscalation(item.escalation.id)}
                />
              </li>
            );
          })}
        </ul>
      )}

      {/* Toast */}
      {toast && (
        <div
          className={`fixed bottom-8 left-1/2 -translate-x-1/2 z-50 px-5 py-3 border smcp text-[11px] tracking-wider row-in
            ${toast.kind === "ok" ? "bg-ink text-paper border-ink" : "bg-brand-pink text-paper border-brand-pink"}`}
        >
          {toast.text}
        </div>
      )}
    </div>
  );
}

function BulkBtn({ children, onClick, accent = false }: { children: React.ReactNode; onClick: () => void; accent?: boolean }) {
  return (
    <button
      onClick={onClick}
      className={`
        smcp text-[10px] px-3 py-1.5 border transition-colors
        ${accent
          ? "border-brand-pink-soft text-brand-pink-soft hover:bg-brand-pink hover:text-paper hover:border-brand-pink"
          : "border-paper/40 text-paper hover:bg-paper hover:text-ink"}
      `}
    >
      {children}
    </button>
  );
}

function Box({ checked, indeterminate = false }: { checked: boolean; indeterminate?: boolean }) {
  return (
    <span
      className={`inline-block w-[14px] h-[14px] border transition-colors
        ${checked || indeterminate ? "bg-ink border-ink" : "border-rule hover:border-ink"}`}
      aria-hidden
    >
      {checked && (
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M3 7.5 L6 10 L11 4" stroke="var(--color-paper)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
      {indeterminate && !checked && (
        <span className="block h-[2px] bg-paper mt-[5px] mx-[2px]" />
      )}
    </span>
  );
}

function Row({
  booking, transfer, isToday, open, selected, onSelect, onToggle, onPatch, onCancel, onDelete, showToast,
}: {
  booking: Booking;
  transfer: Escalation | null;
  isToday: boolean;
  open: boolean;
  selected: boolean;
  onSelect: () => void;
  onToggle: () => void;
  onPatch: (patch: Partial<Booking>) => Promise<boolean>;
  onCancel: () => void;
  onDelete: () => void;
  showToast: (kind: "ok" | "err", text: string) => void;
}) {
  const fullName = [booking.title, booking.first_name, booking.last_name].filter(Boolean).join(" ");

  return (
    <div
      className={`
        group relative
        ${isToday ? "bg-paper-soft" : ""}
        ${open ? "bg-paper-tint/40" : selected ? "bg-paper-soft" : "hover:bg-paper-soft"}
        transition-colors duration-200
      `}
    >
      <span
        aria-hidden
        className={`
          absolute left-0 top-0 bottom-0 transition-all duration-300
          ${open ? "bg-brand-green w-[3px]" : selected ? "bg-brand-green-soft w-[2px]" : "w-px bg-transparent group-hover:bg-brand-green-soft"}
        `}
      />

      <div className="grid grid-cols-[28px_1.3fr_1.7fr_1.8fr_1.8fr_0.7fr_28px] gap-x-4 items-center px-2 py-4">
        {/* Checkbox (separate click target) */}
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onSelect(); }}
          className="flex items-center justify-center"
          aria-label={selected ? "Deselect" : "Select"}
        >
          <Box checked={selected} />
        </button>

        {/* Rest of row toggles details */}
        <button
          type="button"
          onClick={onToggle}
          className="contents text-left"
          aria-expanded={open}
        >
          <span className="flex flex-col">
            <span className="font-mono text-[12px] text-ink-soft tnum tracking-tight">{booking.booking_ref}</span>
            <span className="mt-1.5">
              <ContextTag
                duringHours={booking.during_hours}
                kind={
                  booking.transfer_attempted
                    ? "in-hours-no-answer"
                    : booking.during_hours
                      ? "in-hours-request"
                      : "out-of-hours-request"
                }
              />
            </span>
          </span>

          <span className="flex flex-col min-w-0">
            <span className="font-display text-base text-ink leading-tight truncate">{fullName}</span>
            <span className="font-mono text-[12px] text-ink-mute mt-1 tnum">{booking.phone}</span>
          </span>

          <span className="flex flex-col min-w-0">
            <span className="text-[14px] text-ink-soft leading-tight truncate">{booking.service_name}</span>
            <span className="smcp text-ink-mute text-[10px] mt-1">{booking.service_code}</span>
          </span>

          <span className="flex flex-col min-w-0">
            {booking.requested_ranges ? (
              <span className="font-display italic text-ink text-[14px] leading-snug line-clamp-2">
                {booking.requested_ranges}
              </span>
            ) : booking.appointment_date ? (
              <>
                <span className="text-[13px] text-ink leading-tight">{formatDate(booking.appointment_date)}</span>
                <span className="font-mono text-[12px] text-ink-soft tnum mt-1">{formatTime(booking.appointment_time ?? "00:00:00")}</span>
              </>
            ) : (
              <span className="text-[12px] text-ink-mute italic">no preference recorded</span>
            )}
          </span>

          <span><StatusTag status={booking.status} /></span>

          <span className={`text-ink-mute transition-transform duration-300 ${open ? "rotate-90" : ""}`} aria-hidden>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4">
              <path d="M9 6 L15 12 L9 18" strokeLinecap="round" />
            </svg>
          </span>
        </button>
      </div>

      <div className={`expand-row ${open ? "open" : ""}`}>
        <div className="expand-inner">
          <div className="px-2 pb-7 pt-1">
            <ExpandedPanel booking={booking} onPatch={onPatch} onCancel={onCancel} onDelete={onDelete} showToast={showToast} />
          </div>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Expanded panel — utility-first edit form
   ============================================================ */

function ExpandedPanel({
  booking, onPatch, onCancel, onDelete, showToast,
}: {
  booking: Booking;
  onPatch: (patch: Partial<Booking>) => Promise<boolean>;
  onCancel: () => void;
  onDelete: () => void;
  showToast: (kind: "ok" | "err", text: string) => void;
}) {
  return (
    <div className="border border-rule bg-paper-soft p-6">
      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr_0.9fr] gap-x-10 gap-y-8">
        <PatientBlock booking={booking} onPatch={onPatch} />
        <BookingBlock booking={booking} onPatch={onPatch} />
        <ActionsBlock booking={booking} onPatch={onPatch} onCancel={onCancel} onDelete={onDelete} showToast={showToast} />
      </div>

      <Hairline className="my-7" />

      <NotesBlock booking={booking} onPatch={onPatch} />
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="smcp text-ink-mute text-[10px] mb-3 flex items-center gap-3">
      <span>{children}</span>
      <span className="hairline flex-1" />
    </h3>
  );
}

function PatientBlock({ booking, onPatch }: { booking: Booking; onPatch: (p: Partial<Booking>) => Promise<boolean> }) {
  return (
    <div>
      <SectionTitle>contact</SectionTitle>
      <div className="grid grid-cols-[80px_1fr_80px_1.4fr] gap-x-3 gap-y-2.5 items-baseline">
        <Label>title</Label>
        <SelectField
          value={booking.title ?? ""}
          options={["", "Ms", "Mrs", "Miss", "Mr", "Dr", "Other"]}
          onCommit={(v) => onPatch({ title: v || null })}
        />
        <Label>dob</Label>
        <DateField
          value={booking.date_of_birth ?? ""}
          onCommit={(v) => onPatch({ date_of_birth: v || null })}
        />

        <Label>first</Label>
        <TextField value={booking.first_name} onCommit={(v) => onPatch({ first_name: v })} />
        <Label>last</Label>
        <TextField value={booking.last_name} onCommit={(v) => onPatch({ last_name: v })} />

        <Label>email</Label>
        <div className="col-span-3 flex items-center gap-2">
          <TextField value={booking.email} onCommit={(v) => onPatch({ email: v })} className="flex-1" />
          <CopyBtn value={booking.email} />
          <a href={`mailto:${booking.email}`} className="smcp text-[10px] text-ink-soft hover:text-brand-pink border border-rule hover:border-brand-pink px-2.5 py-1.5 transition-colors" title="Compose email">mail</a>
        </div>

        <Label>phone</Label>
        <div className="col-span-3 flex items-center gap-2">
          <TextField value={booking.phone} onCommit={(v) => onPatch({ phone: v })} className="flex-1" />
          <CopyBtn value={booking.phone} />
          <a href={`tel:${booking.phone}`} className="smcp text-[10px] text-ink-soft hover:text-brand-pink border border-rule hover:border-brand-pink px-2.5 py-1.5 transition-colors" title="Dial">dial</a>
        </div>
      </div>

      <SectionTitle>reason for visit</SectionTitle>
      <TextAreaField
        value={booking.reason_for_visit ?? ""}
        rows={2}
        onCommit={(v) => onPatch({ reason_for_visit: v || null })}
      />
    </div>
  );
}

function BookingBlock({ booking, onPatch }: { booking: Booking; onPatch: (p: Partial<Booking>) => Promise<boolean> }) {
  return (
    <div>
      <SectionTitle>request</SectionTitle>
      <div className="grid grid-cols-[110px_1fr] gap-x-3 gap-y-2.5 items-baseline">
        <Label>ref</Label>
        <span className="font-mono tnum text-[12px] text-ink-soft self-center">{booking.booking_ref}</span>

        <Label>service</Label>
        <SelectField
          value={booking.service_code}
          options={SERVICES.map((s) => s.code)}
          labelFor={(code) => {
            const s = SERVICES.find((x) => x.code === code);
            return s ? s.name : code;
          }}
          onCommit={(code) => {
            const s = SERVICES.find((x) => x.code === code);
            if (!s) return;
            void onPatch({ service_code: s.code, service_name: s.name, service_price_pence: s.price_pence });
          }}
        />

        <Label>their windows</Label>
        <TextAreaField
          value={booking.requested_ranges ?? ""}
          rows={2}
          onCommit={(v) => onPatch({ requested_ranges: v || null })}
          placeholder="caller's preferred availability"
        />

        <Label>scheduled date</Label>
        <DateField
          value={booking.appointment_date ?? ""}
          onCommit={(v) => onPatch({ appointment_date: v || null })}
        />

        <Label>scheduled time</Label>
        <TimeField
          value={booking.appointment_time ?? ""}
          onCommit={(v) => onPatch({ appointment_time: v || null })}
        />

        <Label>length</Label>
        <SelectField
          value={String(booking.duration_minutes)}
          options={["30", "45", "60", "90"]}
          labelFor={(v) => `${v} min`}
          onCommit={(v) => onPatch({ duration_minutes: Number(v) })}
        />

        <Label>captured</Label>
        <span className="text-[12px] text-ink-mute self-center tnum">
          {formatRelative(booking.created_at)} <span className="ml-1">via voice agent</span>
        </span>
      </div>
    </div>
  );
}

function ActionsBlock({
  booking, onPatch, onCancel, onDelete, showToast,
}: {
  booking: Booking;
  onPatch: (p: Partial<Booking>) => Promise<boolean>;
  onCancel: () => void;
  onDelete: () => void;
  showToast: (kind: "ok" | "err", text: string) => void;
}) {
  return (
    <div className="lg:border-l lg:border-rule lg:pl-8">
      <SectionTitle>workflow</SectionTitle>

      <div className="flex flex-col gap-2">
        <ActionBtn
          variant="primary"
          disabled={booking.status === "invited"}
          onClick={() => onPatch({ status: "invited" })}
        >
          sent invite
        </ActionBtn>

        <ActionBtn
          variant="primary"
          disabled={booking.status === "scheduled"}
          onClick={() => onPatch({ status: "scheduled" })}
        >
          booked in meddbase
        </ActionBtn>

        {booking.status !== "pending" && (
          <ActionBtn variant="ghost" onClick={() => onPatch({ status: "pending" })}>
            revert to pending
          </ActionBtn>
        )}

        <ActionBtn
          variant="danger"
          disabled={booking.status === "cancelled"}
          onClick={() => {
            if (window.confirm(`Cancel ${booking.booking_ref}? The patient will NOT be notified automatically.`)) {
              onCancel();
            }
          }}
        >
          cancel request
        </ActionBtn>

        <Hairline className="my-3" />

        <ActionBtn
          variant="ghost"
          onClick={() => {
            const summary = formatSummary(booking);
            navigator.clipboard.writeText(summary);
            showToast("ok", "Request summary copied.");
          }}
        >
          copy summary
        </ActionBtn>

        <ActionBtn variant="ghost-danger" onClick={onDelete}>
          delete permanently
        </ActionBtn>
      </div>
    </div>
  );
}

function NotesBlock({ booking, onPatch }: { booking: Booking; onPatch: (p: Partial<Booking>) => Promise<boolean> }) {
  return (
    <div>
      <SectionTitle>internal notes (front desk)</SectionTitle>
      <TextAreaField
        value={booking.notes ?? ""}
        rows={3}
        placeholder="Notes for the team — not visible to the patient."
        onCommit={(v) => onPatch({ notes: v || null })}
      />
    </div>
  );
}

/* ============================================================
   Editable field primitives — debounced commit on blur / Enter.
   ============================================================ */

function Label({ children }: { children: React.ReactNode }) {
  return <span className="smcp text-[10px] text-ink-mute pt-2">{children}</span>;
}

function TextField({
  value, onCommit, className = "", placeholder,
}: { value: string; onCommit: (v: string) => void; className?: string; placeholder?: string }) {
  const [v, setV] = useState(value);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => setV(value), [value]);
  return (
    <input
      ref={ref}
      type="text"
      value={v}
      placeholder={placeholder}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => v !== value && onCommit(v.trim())}
      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); if (e.key === "Escape") { setV(value); ref.current?.blur(); } }}
      className={`bg-transparent border-b border-rule-soft focus:border-ink outline-none px-1 py-1 text-[14px] text-ink ${className}`}
    />
  );
}

function TextAreaField({
  value, onCommit, rows = 2, placeholder,
}: { value: string; onCommit: (v: string) => void; rows?: number; placeholder?: string }) {
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  return (
    <textarea
      rows={rows}
      value={v}
      placeholder={placeholder}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => v !== value && onCommit(v.trim())}
      className="w-full bg-transparent border border-rule-soft focus:border-ink outline-none px-3 py-2 text-[13px] text-ink leading-relaxed resize-none"
    />
  );
}

function SelectField({
  value, options, onCommit, labelFor,
}: {
  value: string;
  options: string[];
  onCommit: (v: string) => void;
  labelFor?: (v: string) => string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onCommit(e.target.value)}
      className="bg-transparent border-b border-rule-soft focus:border-ink outline-none px-1 py-1 text-[14px] text-ink"
    >
      {options.map((o) => (
        <option key={o} value={o} className="text-ink bg-paper-soft">
          {labelFor ? labelFor(o) : o || "—"}
        </option>
      ))}
    </select>
  );
}

function DateField({ value, onCommit }: { value: string; onCommit: (v: string) => void }) {
  return (
    <input
      type="date"
      value={value || ""}
      onChange={(e) => onCommit(e.target.value)}
      className="bg-transparent border-b border-rule-soft focus:border-ink outline-none px-1 py-1 text-[13px] text-ink tnum font-mono"
    />
  );
}

function TimeField({ value, onCommit }: { value: string; onCommit: (v: string) => void }) {
  // Convert HH:MM:SS → HH:MM for input, back to HH:MM:00 on commit
  const v = value ? value.slice(0, 5) : "";
  return (
    <input
      type="time"
      value={v}
      step={1800}
      onChange={(e) => onCommit(e.target.value ? `${e.target.value}:00` : "")}
      className="bg-transparent border-b border-rule-soft focus:border-ink outline-none px-1 py-1 text-[13px] text-ink tnum font-mono"
    />
  );
}

function CopyBtn({ value }: { value: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        void navigator.clipboard.writeText(value);
        setDone(true);
        setTimeout(() => setDone(false), 1200);
      }}
      className="smcp text-[10px] text-ink-soft hover:text-brand-green border border-rule hover:border-brand-green px-2.5 py-1.5 transition-colors"
      title="Copy"
    >
      {done ? "copied" : "copy"}
    </button>
  );
}

function ActionBtn({
  children, onClick, disabled = false, variant = "primary",
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  variant?: "primary" | "ghost" | "danger" | "ghost-danger";
}) {
  const styles =
    variant === "primary"
      ? "border-forest text-forest hover:bg-forest hover:text-paper"
      : variant === "danger"
        ? "border-brand-pink text-brand-pink hover:bg-brand-pink hover:text-paper"
        : variant === "ghost-danger"
          ? "border-rule text-brand-pink hover:border-brand-pink"
          : "border-rule text-ink-soft hover:border-ink hover:text-ink";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`smcp text-[11px] py-2.5 px-3 border transition-colors duration-300 disabled:opacity-30 disabled:cursor-not-allowed ${styles}`}
    >
      {children}
    </button>
  );
}

function formatSummary(b: Booking): string {
  const fullName = [b.title, b.first_name, b.last_name].filter(Boolean).join(" ");
  const when = b.appointment_date
    ? `${formatDate(b.appointment_date)} · ${formatTime(b.appointment_time ?? "")}`
    : (b.requested_ranges ?? "no preference recorded");
  return [
    `Request ${b.booking_ref}`,
    `Patient: ${fullName}`,
    `DOB: ${b.date_of_birth ?? "—"}`,
    `Email: ${b.email}`,
    `Phone: ${b.phone}`,
    `Service: ${b.service_name} (${b.service_code})`,
    `Their availability: ${when}`,
    `Status: ${b.status}`,
    b.reason_for_visit ? `Reason: ${b.reason_for_visit}` : "",
    b.notes ? `Notes: ${b.notes}` : "",
  ].filter(Boolean).join("\n");
}

function EmptyState() {
  return (
    <div className="py-24 flex flex-col items-center justify-center text-center">
      <svg width="56" height="56" viewBox="0 0 56 56" className="text-rule mb-6" aria-hidden>
        <circle cx="28" cy="28" r="26" fill="none" stroke="currentColor" strokeWidth="0.7" />
        <path d="M16 28 C 16 22, 22 16, 28 16 S 40 22, 40 28 S 34 40, 28 40 S 16 34, 16 28 Z"
          fill="none" stroke="currentColor" strokeWidth="0.5" strokeDasharray="2 3" />
      </svg>
      <p className="font-display italic text-ink-soft text-xl mb-2">The ledger is quiet.</p>
      <p className="text-ink-mute text-sm max-w-sm">No entries match this view. Try widening the date range or clearing the search.</p>
    </div>
  );
}

/* ============================================================
   Context tags — show at-a-glance how this entry came in
   ============================================================ */

type ContextKind =
  | "in-hours-request"        // Sophia took a request during work hours (toggled on)
  | "out-of-hours-request"    // Sophia took a request out of hours
  | "in-hours-no-answer"      // Transfer attempted in-hours, no answer, then request taken
  | "transfer-then-request"   // Transfer attempted in-hours, succeeded but request also recorded (rare)
  | "transfer-confirmed"      // Transfer attempted in-hours, succeeded, no request needed
  | "transfer-no-answer"      // Transfer attempted in-hours, no answer, no request collected
  | "callback-request";       // Pure callback request, no booking row

function ContextTag({ kind, duringHours }: { kind: ContextKind; duringHours: boolean | null }) {
  // Kept fully here so each variant is a single read.
  let label: string;
  let style: string;
  switch (kind) {
    case "in-hours-request":
      label = "In hours · request";
      style = "border-brand-green text-forest bg-brand-green/[0.08]";
      break;
    case "out-of-hours-request":
      label = "Out of hours · request";
      style = "border-rule text-ink-soft bg-paper-tint/40";
      break;
    case "in-hours-no-answer":
      label = "In hours · no answer · request";
      style = "border-amber text-amber bg-amber/[0.08]";
      break;
    case "transfer-then-request":
      label = "In hours · transferred · request";
      style = "border-brand-green text-forest bg-brand-green/[0.08]";
      break;
    case "transfer-confirmed":
      label = "Transferred & confirmed";
      style = "border-forest text-forest bg-forest/[0.06]";
      break;
    case "transfer-no-answer":
      label = "In hours · no answer";
      style = "border-amber text-amber bg-amber/[0.08]";
      break;
    case "callback-request":
      label = duringHours ? "In hours · callback" : "Out of hours · callback";
      style = "border-brand-pink text-brand-pink bg-brand-pink/[0.06]";
      break;
  }
  return (
    <span className={`inline-block smcp text-[9px] tracking-wider px-2 py-0.5 border ${style}`}>
      {label}
    </span>
  );
}

/* ============================================================
   EscalationRow — for entries WITHOUT a matching booking
   (successful transfers, or pure callbacks with no details)
   ============================================================ */

function EscalationRow({
  escalation,
  selected,
  onSelect,
  onResolve,
  onDelete,
}: {
  escalation: Escalation;
  selected: boolean;
  onSelect: () => void;
  onResolve: () => void;
  onDelete: () => void;
}) {
  const kind: ContextKind = escalation.transferred
    ? "transfer-confirmed"
    : escalation.during_hours
      ? "transfer-no-answer"
      : "callback-request";

  return (
    <div className={`group relative px-2 py-4 transition-colors duration-200 ${selected ? "bg-paper-soft" : "hover:bg-paper-soft"}`}>
      <span aria-hidden className="absolute left-0 top-0 bottom-0 w-px bg-transparent group-hover:bg-rule" />
      <div className="grid grid-cols-[28px_1.3fr_1.7fr_1.8fr_1.8fr_0.7fr_28px] gap-x-4 items-center">
        {/* Checkbox */}
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onSelect(); }}
          className="flex items-center justify-center"
          aria-label={selected ? "Deselect" : "Select"}
        >
          <Box checked={selected} />
        </button>

        <div className="flex flex-col">
          <span className="font-display italic text-ink-mute text-[12px]">— call event —</span>
          <span className="mt-1.5">
            <ContextTag kind={kind} duringHours={escalation.during_hours} />
          </span>
        </div>

        <div className="flex flex-col">
          <span className="font-mono tnum text-[13px] text-ink">{escalation.callback_phone}</span>
          {escalation.caller_phone !== escalation.callback_phone && (
            <span className="font-mono tnum text-[11px] text-ink-mute mt-0.5">
              calling-from {escalation.caller_phone}
            </span>
          )}
        </div>

        <span className="font-display italic text-ink-soft text-sm leading-snug line-clamp-2">
          {escalation.reason || <em>no reason recorded</em>}
        </span>

        <span className="text-[12px] text-ink-mute tnum">{formatRelative(escalation.created_at)}</span>

        <span className="smcp text-[10px] text-ink-mute">
          {escalation.status}
        </span>

        <span aria-hidden />
      </div>

      <div className="ml-[28px] mt-3 flex items-center gap-2 flex-wrap">
        <a
          href={`tel:${escalation.callback_phone}`}
          className="smcp text-[10px] text-paper bg-ink hover:bg-brand-pink hover:border-brand-pink border border-ink px-3 py-1.5 transition-colors"
        >
          call back
        </a>
        {escalation.status !== "resolved" && (
          <button
            onClick={onResolve}
            className="smcp text-[10px] text-forest border border-rule hover:border-forest hover:bg-forest hover:text-paper px-2.5 py-1.5 transition-colors"
          >
            mark resolved
          </button>
        )}
        <button
          onClick={onDelete}
          className="smcp text-[10px] text-brand-pink border border-rule hover:border-brand-pink hover:bg-brand-pink hover:text-paper px-2.5 py-1.5 transition-colors"
        >
          delete
        </button>
      </div>
    </div>
  );
}
