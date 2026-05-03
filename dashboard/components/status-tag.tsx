type Status = "pending" | "invited" | "scheduled" | "confirmed" | "cancelled" | "declined";

type StatusTagProps = {
  status: Status;
  size?: "sm" | "md";
};

const labels: Record<Status, string> = {
  pending: "pending",
  invited: "invited",
  scheduled: "scheduled",
  confirmed: "confirmed",
  cancelled: "cancelled",
  declined: "declined",
};

const colours: Record<Status, { fg: string; rule: string }> = {
  pending:   { fg: "text-amber",       rule: "bg-amber" },
  invited:   { fg: "text-brand-green", rule: "bg-brand-green" },
  scheduled: { fg: "text-forest",      rule: "bg-forest" },
  confirmed: { fg: "text-forest",      rule: "bg-forest" },
  cancelled: { fg: "text-claret",      rule: "bg-claret" },
  declined:  { fg: "text-brand-pink",  rule: "bg-brand-pink" },
};

/**
 * Status indicator. Deliberately NOT pill-shaped (avoids the SaaS look). Reads as
 * a small-caps annotation with a coloured underline rule, like a footnote.
 */
export function StatusTag({ status, size = "md" }: StatusTagProps) {
  const c = colours[status] ?? colours.pending;
  const sz = size === "sm" ? "text-[10px]" : "text-[11px]";

  return (
    <span className="inline-flex flex-col items-start">
      <span className={`smcp ${c.fg} ${sz} font-medium leading-tight`}>{labels[status] ?? status}</span>
      <span className={`mt-1 h-px w-7 ${c.rule} opacity-70`} />
    </span>
  );
}
