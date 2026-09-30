import { CircleCheck, TriangleAlert, Undo2, Zap } from "lucide-react";
import { SCENARIOS, triggerScenario, type ScenarioId } from "../../lib/api";
import { useStore } from "../../lib/store";

const ICON: Record<ScenarioId, typeof Zap> = {
  washer_e3: TriangleAlert,
  washer_done: CircleCheck,
  ac_spike: Zap,
  dryer_done: CircleCheck,
  reset: Undo2,
};
const TONE = { bad: "text-bad", warn: "text-run", ok: "text-ok", neutral: "text-ink-48" } as const;

function useDemoHome(): boolean {
  return useStore((s) => s.hello?.home === "demo");
}

/** The reference's side rail, put to work: break the demo home from any page. Desktop only. */
export function SimulateRail() {
  if (!useDemoHome()) return null;
  return (
    <aside
      aria-label="Simulate something in the demo home"
      className="glass fixed left-5 top-1/2 z-30 hidden -translate-y-1/2 flex-col items-center gap-1 rounded-full p-1.5 lg:flex"
    >
      <span className="t-eyebrow px-1 pb-1 pt-2 text-[9px] text-ink-48">Test</span>
      {SCENARIOS.map((scenario, i) => {
        const Icon = ICON[scenario.id];
        return (
          <button
            key={scenario.id}
            type="button"
            onClick={() => triggerScenario(scenario.id)}
            className="pressable group relative grid h-10 w-10 place-items-center rounded-full hover:bg-white/80"
            aria-label={`${scenario.label} (key ${i + 1})`}
          >
            <Icon size={18} className={TONE[scenario.tone]} aria-hidden="true" />
            <span className="pointer-events-none absolute left-full ml-3 whitespace-nowrap rounded-full bg-ink px-3 py-1.5 t-fine text-white opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100">
              {scenario.label} <kbd className="text-white/50">{i + 1}</kbd>
            </span>
          </button>
        );
      })}
    </aside>
  );
}

/** The same controls as a card, for screens without the rail. */
export function SimulateCard() {
  if (!useDemoHome()) return null;
  return (
    <section className="card p-5 lg:hidden" aria-label="Simulate something in the demo home">
      <h2 className="t-caption-strong">Test the demo home</h2>
      <p className="t-fine mt-1 text-ink-48">Break something, then ask the assistant about it.</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {SCENARIOS.map((scenario) => {
          const Icon = ICON[scenario.id];
          return (
            <button key={scenario.id} type="button" onClick={() => triggerScenario(scenario.id)} className="btn-utility rounded-full">
              <Icon size={15} className={TONE[scenario.tone]} aria-hidden="true" />
              {scenario.label}
            </button>
          );
        })}
      </div>
    </section>
  );
}
