"use client";

type Range = "all" | "today" | "upcoming" | "past";
type Status = "all" | "pending" | "invited" | "scheduled" | "confirmed" | "cancelled" | "declined";

type Props = {
  range: Range;
  status: Status;
  query: string;
  onRange: (r: Range) => void;
  onStatus: (s: Status) => void;
  onQuery: (q: string) => void;
  count: number;
  exportHref?: string;
};

const RANGES: { key: Range; label: string }[] = [
  { key: "all", label: "all" },
  { key: "today", label: "today" },
  { key: "upcoming", label: "upcoming" },
  { key: "past", label: "past" },
];

const STATUSES: { key: Status; label: string }[] = [
  { key: "all", label: "all status" },
  { key: "pending", label: "pending" },
  { key: "invited", label: "invited" },
  { key: "scheduled", label: "scheduled" },
  { key: "cancelled", label: "cancelled" },
];

export function FilterBar({ range, status, query, onRange, onStatus, onQuery, count, exportHref }: Props) {
  return (
    <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between mb-6">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-2">
        <span className="smcp text-ink-mute text-[10px] mr-2">view</span>
        {RANGES.map((r) => (
          <Chip key={r.key} active={range === r.key} onClick={() => onRange(r.key)}>
            {r.label}
          </Chip>
        ))}
        <span className="hairline w-4 mx-3 opacity-50" aria-hidden />
        <span className="smcp text-ink-mute text-[10px] mr-2">status</span>
        {STATUSES.map((s) => (
          <Chip key={s.key} active={status === s.key} onClick={() => onStatus(s.key)}>
            {s.label}
          </Chip>
        ))}
      </div>

      <div className="flex items-center gap-4">
        <span className="smcp text-ink-mute text-[10px] tnum">
          {count} {count === 1 ? "entry" : "entries"}
        </span>
        {exportHref && (
          <a
            href={exportHref}
            className="smcp text-[10px] text-ink-soft hover:text-ink border border-rule hover:border-ink px-3 py-1.5 transition-colors"
            title="Download visible bookings as CSV"
          >
            export csv
          </a>
        )}
        <div className="relative">
          <input
            type="search"
            value={query}
            onChange={(e) => onQuery(e.target.value)}
            placeholder="search name, ref, email…"
            className="input-line w-72 text-sm"
            aria-label="Search bookings"
          />
        </div>
      </div>
    </div>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        smcp text-[11px] px-3 py-1.5
        border transition-all duration-200
        ${active
          ? "border-ink bg-ink text-paper"
          : "border-rule text-ink-soft hover:border-ink hover:text-ink"}
      `}
    >
      {children}
    </button>
  );
}
