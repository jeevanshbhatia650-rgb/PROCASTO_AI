import { useCountUp } from "../../hooks/useCountUp";
import { formatSeconds } from "../../lib/format";
import { useStore } from "../../lib/store";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="t-fine text-white/50">{label}</p>
      <p className="t-caption-strong tabular mt-0.5 text-white">{value}</p>
    </div>
  );
}

const SAME_MOMENT_MS = 50;

function firstAnswer(ms: number | null): string {
  if (ms == null) return "–";
  if (Math.abs(ms) < SAME_MOMENT_MS) return "as you finished";
  return `${formatSeconds(ms)} ${ms < 0 ? "before you finished" : "after you finished"}`;
}

/** A correction that names the device as its last word can't start early; say so plainly. */
function lastQuestion(ms: number | null): string {
  if (ms == null) return "–";
  return ms < SAME_MOMENT_MS ? "as you finished" : `${formatSeconds(ms)} early`;
}

/** F20: the headline proof. How long before the end of your sentence the first grounded lookup fired. */
export function LeadTimeBadge() {
  const metrics = useStore((s) => s.metrics);
  const best = metrics.best_lead_time_ms;
  const shown = useCountUp(best ?? 0);
  const last = metrics.lead_time_ms;
  const firstCard = metrics.first_card_ms;
  const resumed = metrics.tasks_reused + metrics.tasks_refetched > 0;
  const hearing = useStore((s) => s.transcript !== null && !s.transcript.final);
  let caption = "Retrieval started this long before you finished speaking.";
  if (best == null) {
    caption = hearing
      ? "Measuring while you talk. It's scored when you finish."
      : "Ask something. The clock starts at your first word.";
  }

  return (
    <div>
      <p className="t-eyebrow text-white/50">Head start</p>
      <p className="t-hero tabular mt-1 text-white">{best == null ? "–" : `${(shown / 1000).toFixed(1)} s`}</p>
      <p className="t-body mt-1 text-body-muted">{caption}</p>
      <div className="mt-5 grid grid-cols-3 gap-4 border-t border-white/10 pt-4">
        <Stat label="Last question" value={lastQuestion(last)} />
        <Stat label="First answer" value={firstAnswer(firstCard)} />
        <Stat
          label="On resume"
          value={resumed ? `${metrics.tasks_reused} reused · ${metrics.tasks_refetched} refetched` : "–"}
        />
      </div>
    </div>
  );
}
