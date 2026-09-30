import { Link } from "react-router";

/** A pulse inside a rounded square: a home that answers. */
function LogoMark({ size = 28, inverted = false }: { size?: number; inverted?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill={inverted ? "#fff" : "#111113"} />
      <path
        d="M6 17h5l2.5-6 4 11 2.5-5H26"
        fill="none"
        stroke={inverted ? "#111113" : "#fff"}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Logo({ to = "/", inverted = false }: { to?: string; inverted?: boolean }) {
  return (
    <Link to={to} className="pressable inline-flex items-center gap-2.5 rounded-full" aria-label="PROCASTO home">
      <LogoMark inverted={inverted} />
      <span className={`font-display text-[15px] font-semibold tracking-[0.14em] ${inverted ? "text-white" : "text-ink"}`}>
        PROCASTO
      </span>
    </Link>
  );
}
