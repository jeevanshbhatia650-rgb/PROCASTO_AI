import type { ReactNode } from "react";

type Props = {
  value: number; // 0..1
  size?: number;
  stroke?: number;
  tone?: "ink" | "white" | "bad" | "ok" | "run";
  label: string; // what the ring measures, for screen readers
  children?: ReactNode;
};

const TONE: Record<NonNullable<Props["tone"]>, [track: string, bar: string]> = {
  ink: ["rgb(17 17 19 / 0.08)", "#111113"],
  white: ["rgb(255 255 255 / 0.14)", "#ffffff"],
  bad: ["rgb(229 55 43 / 0.14)", "#e5372b"],
  ok: ["rgb(47 179 90 / 0.16)", "#2fb35a"],
  run: ["rgb(232 137 12 / 0.16)", "#e8890c"],
};

/** A progress ring like the reference's 90 % / 65 % dials, with anything centred inside it. */
export function Ring({ value, size = 112, stroke = 9, tone = "ink", label, children }: Props) {
  const r = (size - stroke) / 2;
  const length = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(1, value));
  const [track, bar] = TONE[tone];
  return (
    <div
      className="relative grid shrink-0 place-items-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${label}: ${Math.round(clamped * 100)}%`}
    >
      <svg className="absolute inset-0" width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={bar}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${length * clamped} ${length}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dasharray 600ms var(--ease-out)" }}
        />
      </svg>
      <div className="relative text-center">{children}</div>
    </div>
  );
}
