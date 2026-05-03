/**
 * Tiny decorative primitives — reused across pages so the editorial / letterpress
 * feel stays consistent.
 */

export function DoubleRule({ className = "" }: { className?: string }) {
  return <div className={`double-rule ${className}`} aria-hidden="true" />;
}

export function Hairline({ className = "" }: { className?: string }) {
  return <div className={`hairline ${className}`} aria-hidden="true" />;
}

/** Centred ornamental divider (✦), used between sections on the login screen. */
export function Ornament({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center justify-center gap-3 ${className}`} aria-hidden="true">
      <span className="hairline flex-1 max-w-16" />
      <svg width="14" height="14" viewBox="0 0 24 24" className="text-brand-green">
        <path
          d="M12 2 C 14 8, 18 10, 22 12 C 18 14, 14 16, 12 22 C 10 16, 6 14, 2 12 C 6 10, 10 8, 12 2 Z"
          fill="currentColor"
        />
      </svg>
      <span className="hairline flex-1 max-w-16" />
    </div>
  );
}

export function CornerFlourish({ className = "" }: { className?: string }) {
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" className={className} aria-hidden="true">
      <path
        d="M2 2 L2 14 M2 2 L14 2 M16 2 Q22 2 26 6 T30 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="0.6"
      />
    </svg>
  );
}
