import Image from "next/image";

type WordmarkProps = {
  size?: "sm" | "md" | "lg";
  showSubtitle?: boolean;
  className?: string;
};

/**
 * Header wordmark. Renders the official egynaecologist logo (PNG, served from /public)
 * paired with a small-caps subtitle so the front-desk context is clear without restating
 * the brand name. Letter-press fade-in on first paint.
 */
export function Wordmark({ size = "md", showSubtitle = true, className = "" }: WordmarkProps) {
  const dims = {
    sm: { w: 132, h: 44, sub: "text-[9px]" },
    md: { w: 192, h: 64, sub: "text-[10px]" },
    lg: { w: 280, h: 93, sub: "text-[11px]" },
  }[size];

  return (
    <div className={`flex flex-col items-start gap-2 letter-press ${className}`}>
      <Image
        src="/logo.png"
        alt="egynaecologist"
        width={dims.w}
        height={dims.h}
        priority
        className="select-none"
      />
      {showSubtitle && (
        <span className={`smcp text-ink-mute ${dims.sub} pl-0.5`}>
          front desk · bookings ledger
        </span>
      )}
    </div>
  );
}
