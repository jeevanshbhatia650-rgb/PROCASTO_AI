import { useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import { useNow } from "../../hooks/useNow";
import { formatSeconds } from "../../lib/format";
import { clearOf, FLIP_AT_PCT, labelWidth, placeLabels, type Side } from "../../lib/labels";
import { useStore } from "../../lib/store";
import { buildWaterfall, utterances, type Marker, type Waterfall } from "../../lib/waterfall";
import type { TaskStatus } from "../../types/generated";

const LABEL_W = 132;
const FINISHED = "you finished";
const MAX_BARS = 6;
const BAR_COLOR: Record<TaskStatus, string> = {
  pending: "bg-white/30",
  running: "bg-run-dark",
  done: "bg-ok-dark",
  cancelled: "bg-off",
  parked: "bg-primary-on-dark",
  stale: "bg-bad-dark/70",
};
const TONE_COLOR: Record<Marker["tone"], string> = {
  bad: "bg-bad-dark",
  info: "bg-white/70",
  park: "bg-primary-on-dark",
};

function useWidth<T extends HTMLElement>(): [RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry?.contentRect.width ?? 0));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex h-7 items-center">
      <div className="t-fine shrink-0 truncate pr-3 text-white/55" style={{ width: LABEL_W }} title={label}>
        {label}
      </div>
      <div className="relative h-full flex-1">{children}</div>
    </div>
  );
}

function Mark({ at, side, label, children }: { at: number; side: Side; label: string; children: ReactNode }) {
  return (
    <span className="absolute top-1/2 -translate-y-1/2" style={{ left: `${at}%` }}>
      {children}
      {side && (
        <span
          className={`t-fine absolute top-1/2 -translate-y-1/2 whitespace-nowrap text-white/85 ${
            side === "right" ? "left-full ml-1" : "right-full mr-1"
          }`}
        >
          {label}
        </span>
      )}
    </span>
  );
}

function Chart({ w, nowMs, live }: { w: Waterfall; nowMs: number; live: boolean }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const chartPx = Math.max(1, width - LABEL_W);
  const span = w.end - w.start;
  const pct = (t: number) => Math.max(0, Math.min(100, ((t - w.start) / span) * 100));
  const step = span < 4000 ? 500 : span < 8000 ? 1000 : 2000;
  const origin = w.start + 200;
  const ticks: number[] = [];
  for (let t = origin; t <= w.end; t += step) ticks.push(t);
  const bars = w.bars.slice(-MAX_BARS);
  const firstStart = w.leadMs !== null && w.spokeEnd !== null ? w.spokeEnd - w.leadMs : null;
  const px = (t: number) => (pct(t) / 100) * chartPx;
  const wordSides = placeLabels(w.words.map((x) => pct(x.t)), w.words.map((x) => x.text), chartPx);
  const clauseSides = placeLabels(w.clauses.map((x) => pct(x.t)), w.clauses.map((x) => x.label), chartPx, true);
  const eventSides = placeLabels(w.events.map((x) => pct(x.t)), w.events.map((x) => x.label), chartPx, true);
  const endPct = w.spokeEnd !== null ? pct(w.spokeEnd) : null;
  const endSide = endPct !== null && endPct > FLIP_AT_PCT ? "left" : "right";
  // Axis labels make room for the "you finished" label instead of colliding with it.
  const shownTicks = ticks.filter(
    (t) => w.spokeEnd === null || clearOf(px(t), px(w.spokeEnd), labelWidth(FINISHED), endSide),
  );

  return (
    <div ref={ref} className="relative mt-4">
      <Row label="">
        {shownTicks.map((t) => (
          <span
            key={t}
            className="t-fine tabular absolute top-1 -translate-x-1/2 whitespace-nowrap text-white/35"
            style={{ left: `${pct(t)}%` }}
          >
            {((t - origin) / 1000).toFixed(1)} s
          </span>
        ))}
      </Row>
      <Row label="You said">
        {w.words.map((word, i) => (
          <Mark key={i} at={pct(word.t)} side={wordSides[i] ?? null} label={word.text}>
            <span className="block h-3 w-px bg-white/40" />
          </Mark>
        ))}
      </Row>
      <Row label="Understood">
        {w.clauses.map((m, i) => (
          <Mark key={i} at={pct(m.t)} side={clauseSides[i] ?? null} label={m.label}>
            <span className={`block h-2 w-2 -translate-x-1/2 rotate-45 ${m.tone === "bad" ? "bg-bad-dark" : "bg-white"}`} />
          </Mark>
        ))}
      </Row>
      {bars.map((bar) => (
        <Row key={bar.id} label={bar.label}>
          <span
            className={`absolute top-1/2 h-3 -translate-y-1/2 rounded-full ${BAR_COLOR[bar.status]}`}
            style={{ left: `${pct(bar.start)}%`, width: `max(4px, ${pct(bar.end) - pct(bar.start)}%)` }}
            title={`${bar.id}: ${bar.status}, ${formatSeconds(bar.end - bar.start)}`}
          />
        </Row>
      ))}
      <Row label="Home">
        {w.events.map((m, i) => (
          <Mark key={i} at={pct(m.t)} side={eventSides[i] ?? null} label={m.label}>
            <span className={`block h-2 w-2 -translate-x-1/2 rounded-full ${TONE_COLOR[m.tone]}`} />
          </Mark>
        ))}
      </Row>
      <div className="pointer-events-none absolute inset-y-0 right-0" style={{ left: LABEL_W }}>
        {endPct !== null && (
          <div className="absolute inset-y-0 border-l border-dashed border-primary-on-dark" style={{ left: `${endPct}%` }}>
            <span
              className={`t-fine absolute -top-1 whitespace-nowrap text-primary-on-dark ${endSide === "left" ? "right-1.5" : "left-1.5"}`}
            >
              {FINISHED}
            </span>
          </div>
        )}
        {live && <div className="absolute inset-y-0 w-px bg-white/50" style={{ left: `${pct(nowMs)}%` }} />}
      </div>
      {firstStart !== null && w.spokeEnd !== null && w.leadMs !== null && w.leadMs > 0 && (
        <Row label="">
          <div
            className="absolute top-1/2 h-px bg-primary-on-dark"
            style={{ left: `${pct(firstStart)}%`, width: `${pct(w.spokeEnd) - pct(firstStart)}%` }}
          >
            <span className="absolute -top-1 left-0 h-2 w-px bg-primary-on-dark" />
            <span className="absolute -top-1 right-0 h-2 w-px bg-primary-on-dark" />
            <span className="t-caption-strong absolute left-1/2 top-1 -translate-x-1/2 whitespace-nowrap text-primary-on-dark">
              {formatSeconds(w.leadMs)} head start
            </span>
          </div>
        </Row>
      )}
    </div>
  );
}

const LEGEND: [string, string][] = [
  ["bg-run-dark", "fetching"],
  ["bg-ok-dark", "done"],
  ["bg-primary-on-dark", "parked"],
  ["bg-bad-dark", "stale"],
  ["bg-off", "cancelled"],
];

/** F20: every word, clause, retrieval and home event of one utterance on one time axis. */
export function Timeline() {
  const timeline = useStore((s) => s.timeline);
  const tasks = useStore((s) => s.tasks);
  const devices = useStore((s) => s.devices);
  const offset = useStore((s) => s.clockOffset);
  const [picked, setPicked] = useState<string | null>(null);
  const all = useMemo(() => utterances(timeline), [timeline]);
  const current = all.find((u) => u.id === picked) ?? all[all.length - 1];
  const live = current !== undefined && current.end === null;
  const now = useNow(live ? 100 : 1000);
  const names = useMemo(
    () => Object.fromEntries(Object.values(devices).map((d) => [d.info.device_id, d.info.display_name])),
    [devices],
  );

  if (!current) {
    return <p className="t-caption mt-4 text-white/55">Ask something to see when each lookup started compared to your words.</p>;
  }
  const next = all[all.indexOf(current) + 1];
  const waterfall = buildWaterfall(timeline, tasks, current, next, now - offset, names);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-1.5">
        {all.slice(-4).map((u) => {
          const selected = u.id === current.id;
          return (
            <button
              key={u.id}
              type="button"
              onClick={() => setPicked(u.id === all[all.length - 1]?.id ? null : u.id)}
              className={`pressable max-w-[180px] truncate rounded-full px-3 py-1 t-fine transition-colors duration-150 ${
                selected ? "bg-white text-ink" : "bg-white/10 text-white/70 hover:bg-white/15"
              }`}
            >
              “{u.text || "…"}”
            </button>
          );
        })}
      </div>
      <Chart w={waterfall} nowMs={now - offset} live={live} />
      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 t-fine text-white/55">
        {LEGEND.map(([color, label]) => (
          <span key={label} className="flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${color}`} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
