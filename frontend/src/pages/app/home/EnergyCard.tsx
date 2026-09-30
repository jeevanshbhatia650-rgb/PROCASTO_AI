import { useState, type PointerEvent } from "react";
import { formatPower } from "../../../lib/format";
import { MAX_POWER_SAMPLES, POWER_SAMPLE_MS, totalPower, useStore } from "../../../lib/store";
import type { DeviceSnapshot } from "../../../types/generated";

const W = 320;
const H = 96;
const PAD = 4;

function agoLabel(index: number, count: number): string {
  const seconds = Math.round(((count - 1 - index) * POWER_SAMPLE_MS) / 1000);
  return seconds === 0 ? "now" : seconds < 60 ? `${seconds} s ago` : `${Math.round(seconds / 60)} min ago`;
}

/**
 * Whole-home power over a fixed two-minute window that fills from the right, so time reads left to right from the
 * first second. One series, a 2px line on a zero baseline with headroom, a crosshair on hover.
 */
function PowerChart({ samples }: { samples: number[] }) {
  const [hover, setHover] = useState<number | null>(null);
  if (samples.length < 2) {
    return (
      <div className="relative mt-3 grid h-24 place-items-center" aria-label="Collecting power readings">
        <span className="absolute inset-x-1 bottom-2 border-t-2 border-dashed border-ink/15" aria-hidden="true" />
        <span className="t-fine text-ink-48">First readings arrive in a few seconds…</span>
      </div>
    );
  }
  const max = Math.max(Math.max(...samples) * 1.6, 500);
  const offset = MAX_POWER_SAMPLES - samples.length; // empty slots on the left until the window fills
  const x = (i: number) => PAD + ((offset + i) / (MAX_POWER_SAMPLES - 1)) * (W - 2 * PAD);
  const y = (v: number) => H - PAD - (v / max) * (H - 2 * PAD);
  const line = samples.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = `${line} L${x(samples.length - 1).toFixed(1)},${H} L${x(0).toFixed(1)},${H} Z`;
  const peak = Math.max(...samples);

  const onMove = (event: PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const rel = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    const slot = Math.round(rel * (MAX_POWER_SAMPLES - 1)) - offset;
    setHover(slot < 0 ? null : Math.min(samples.length - 1, slot));
  };
  const at = hover ?? null;
  const left = at === null ? 0 : (x(at) / W) * 100;

  return (
    <div className="relative mt-3 touch-none" onPointerMove={onMove} onPointerDown={onMove} onPointerLeave={() => setHover(null)}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="block h-24 w-full"
        role="img"
        aria-label={`Whole-home power, last ${Math.round((samples.length * POWER_SAMPLE_MS) / 60000)} minutes: now ${formatPower(samples.at(-1))}, peak ${formatPower(peak)}`}
      >
        <defs>
          <linearGradient id="power-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#111113" stopOpacity="0.12" />
            <stop offset="1" stopColor="#111113" stopOpacity="0" />
          </linearGradient>
        </defs>
        <line x1="0" x2={W} y1={H - PAD} y2={H - PAD} stroke="rgb(17 17 19 / 0.1)" vectorEffect="non-scaling-stroke" />
        <path d={area} fill="url(#power-fill)" />
        <path d={line} fill="none" stroke="#111113" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
        {at !== null && (
          <line x1={x(at)} x2={x(at)} y1="0" y2={H} stroke="rgb(17 17 19 / 0.3)" vectorEffect="non-scaling-stroke" />
        )}
      </svg>
      {at !== null && (
        <>
          <span
            className="pointer-events-none absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-ink"
            style={{ left: `${left}%`, top: `${(y(samples[at] ?? 0) / H) * 100}%` }}
            aria-hidden="true"
          />
          <span
            className="pointer-events-none absolute -top-9 -translate-x-1/2 whitespace-nowrap rounded-full bg-ink px-2.5 py-1 t-fine text-white"
            style={{ left: `${Math.min(88, Math.max(12, left))}%` }}
          >
            {formatPower(samples[at])} · {agoLabel(at, samples.length)}
          </span>
        </>
      )}
    </div>
  );
}

const TOP_USERS = 4;

export function EnergyCard() {
  const devices = useStore((s) => s.devices);
  const samples = useStore((s) => s.power);
  const watts = (d: DeviceSnapshot) => Number(d.attributes.power_w) || 0;
  // Only devices that report power, biggest first: a home with thirty lights still reads at a glance.
  const list = Object.values(devices)
    .filter((d) => d.attributes.power_w != null)
    .sort((a, b) => watts(b) - watts(a))
    .slice(0, TOP_USERS);
  const total = totalPower(devices);
  const biggest = Math.max(1, ...list.map(watts));

  return (
    <section className="card flex h-full flex-col p-5 sm:p-6" aria-labelledby="energy-title">
      <p id="energy-title" className="t-eyebrow text-ink-48">
        Power right now
      </p>
      <p className="t-title tabular mt-1">{formatPower(total)}</p>
      <p className="t-fine text-ink-48">Whole home · last 2 minutes</p>
      <PowerChart samples={samples} />
      <ul className="mt-auto space-y-2.5 pt-4">
        {list.map((d) => (
          <li key={d.info.device_id} className="grid grid-cols-[88px_1fr_64px] items-center gap-3 t-fine">
            <span className="truncate text-ink-80">{d.info.display_name}</span>
            <span className="h-1.5 rounded-full bg-ink/[0.07]">
              <span
                className="block h-full origin-left rounded-full bg-ink transition-transform duration-500 ease-out"
                style={{ transform: `scaleX(${watts(d) / biggest})` }}
              />
            </span>
            <span className="tabular text-right text-ink-80">{formatPower(watts(d))}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
