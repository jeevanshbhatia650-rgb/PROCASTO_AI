import { BrainCircuit, DatabaseZap, Radio, SlidersHorizontal, type LucideIcon } from "lucide-react";
import { useStore } from "../../lib/store";

function Row({ Icon, title, children }: { Icon: LucideIcon; title: string; children: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-ink/[0.06] text-ink">
        <Icon size={17} aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="t-caption-strong">{title}</p>
        <div className="t-fine text-ink-48">{children}</div>
      </div>
    </li>
  );
}

const HABIT: Record<string, (v: unknown) => string> = {
  usual_cycle: (v) => `usual cycle ${String(v)}`,
  usual_temp_c: (v) => `usually ${String(v)} °C`,
  preferred_target_c: (v) => `likes ${String(v)} °C`,
};
const habit = (key: string, value: unknown) => HABIT[key]?.(value) ?? `${key.replace(/_/g, " ")} ${String(value)}`;

/** Under the hood: the three agents' memory at work, live. */
export function AgentsStats() {
  const stats = useStore((s) => s.agentsStats);
  const devices = useStore((s) => s.devices);
  if (!stats) return null;
  const cache = stats.cache;
  const prefs = Object.entries(stats.preferences);
  return (
    <section className="card p-5" aria-label="The three agents">
      <h3 className="t-caption-strong">The three agents</h3>
      <p className="t-fine mt-0.5 text-ink-48">Each owns one kind of data and uses the retrieval that suits it. They run side by side.</p>
      <ul className="mt-4 space-y-3.5">
        <Row Icon={Radio} title="Home State · pushed, not polled">
          {stats.push ? "SmartThings sends every change to us (webhooks)" : "The simulator pushes every change"}, so a read is instant.
        </Row>
        <Row Icon={DatabaseZap} title="Manual · semantic cache">
          {cache
            ? `${cache.hits} reused, ${cache.misses} searched${cache.hit_rate !== null ? ` (${Math.round(cache.hit_rate * 100)}% hit rate)` : ""}. Reuse needs ≥ 0.60 similarity and the same code.`
            : "Off"}
        </Row>
        <Row Icon={BrainCircuit} title="Slow Thinker · prefetch by session intent">
          {cache ? `${cache.prefetched} warmed ahead, ${cache.prefetch_hits} used` : "Off"}
          {stats.domains.length > 0 && ` · this session is about ${stats.domains.join(" and ")}`}
        </Row>
        <Row Icon={SlidersHorizontal} title="Preferences · key-value store">
          {prefs.length === 0
            ? "Nothing remembered yet. Confirmed actions teach it."
            : prefs.map(([id, values]) => (
                <span key={id} className="block">
                  {devices[id]?.info.display_name ?? id}: {Object.entries(values).map(([k, v]) => habit(k, v)).join(", ")}
                </span>
              ))}
        </Row>
      </ul>
    </section>
  );
}
