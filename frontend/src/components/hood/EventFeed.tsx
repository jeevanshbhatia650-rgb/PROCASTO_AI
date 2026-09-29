import { useMemo } from "react";
import { describe, type FeedLine } from "../../lib/events";
import { useStore } from "../../lib/store";

const MAX_LINES = 8;
const DOT: Record<FeedLine["tone"], string> = {
  bad: "bg-bad",
  warn: "bg-run",
  info: "bg-off",
  park: "bg-primary",
  ok: "bg-ok",
};

/** F9 + F14: what changed in the home and how the engine reacted (invalidations, stale drops, parks). */
export function EventFeed() {
  const timeline = useStore((s) => s.timeline);
  const devices = useStore((s) => s.devices);
  const lines = useMemo(() => {
    const names = Object.fromEntries(Object.values(devices).map((d) => [d.info.device_id, d.info.display_name]));
    const out: FeedLine[] = [];
    for (let i = timeline.length - 1; i >= 0 && out.length < MAX_LINES; i--) {
      const event = timeline[i];
      const line = event ? describe(event, names) : null;
      if (line) out.push(line);
    }
    return out;
  }, [timeline, devices]);

  return (
    <section className="card p-5" aria-label="What changed">
      <h3 className="t-caption-strong">What changed</h3>
      <p className="t-fine mt-0.5 text-ink-48">When the home changes, answers that depend on it are re-checked by themselves.</p>
      {lines.length === 0 && <p className="t-caption mt-3 text-ink-48">Quiet so far. Try “Washer E3” below.</p>}
      <ul className="mt-3 space-y-2">
        {lines.map((line) => (
          <li key={line.key} className="flex items-start gap-3 t-caption">
            <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${DOT[line.tone]}`} />
            <span className="min-w-0 flex-1 text-ink-80">{line.text}</span>
            <span className="t-fine tabular shrink-0 text-ink-48">{(line.t / 1000).toFixed(1)} s</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
