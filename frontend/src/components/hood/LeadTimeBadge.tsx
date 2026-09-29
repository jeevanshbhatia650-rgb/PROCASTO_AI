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

/** F20: the headline proof. How long before the end of your sentence the first grounded lookup fired. */
export function LeadTimeBadge() {
  const metrics = useStore((s) => s.metrics);
  const best = metrics.best_lead_time_ms;
  const shown = useCountUp(best ?? 0);
  const last = metrics.lead_time_ms;
  const firstCard = metrics.first_card_ms;
  const resumed = metrics.tasks_reused + metrics.tasks_refetched > 0;

  return (
    <div>
      <p className="t-eyebrow text-white/50">Head start</p>
      <p className="t-hero tabular mt-1 text-white">{best == null ? "–" : `${(shown / 1000).toFixed(1)} s`}</p>
      <p className="t-body mt-1 text-body-muted">
        {best == null
          ? "Ask something. The clock starts at your first word."
          : "Retrieval started this long before you finished speaking."}
      </p>
      <div className="mt-5 grid grid-cols-3 gap-4 border-t border-white/10 pt-4">
        <Stat label="Last question" value={last == null ? "–" : `${formatSeconds(last)} early`} />
        <Stat label="First answer" value={firstAnswer(firstCard)} />
        <Stat
          label="On resume"
          value={resumed ? `${metrics.tasks_reused} reused · ${metrics.tasks_refetched} refetched` : "–"}
        />
      </div>
    </div>
  );
}
