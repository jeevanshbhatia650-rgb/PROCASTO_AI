import { SCENARIOS, triggerScenario } from "../../lib/api";
import { useStore } from "../../lib/store";

const TONE_DOT = { bad: "bg-bad", warn: "bg-run", ok: "bg-ok", neutral: "bg-off" } as const;

/** F2: the break-something bar. Faults hit the simulated home; watch the answers react on their own. */
export function ChaosPanel() {
  const provider = useStore((s) => s.hello?.provider);
  if (provider === "smartthings") return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-30 flex justify-center px-4">
      <div
        role="toolbar"
        aria-label="Break something in the simulated home"
        className="frosted pointer-events-auto flex max-w-full items-center gap-1.5 overflow-x-auto rounded-full border border-black/[0.08] p-1.5"
      >
        <span className="t-eyebrow hidden shrink-0 px-3 text-ink-48 sm:inline">Break something</span>
        {SCENARIOS.map((scenario, i) => (
          <button
            key={scenario.id}
            type="button"
            onClick={() => void triggerScenario(scenario.id)}
            className="btn-utility shrink-0 rounded-full"
          >
            <span className={`h-1.5 w-1.5 rounded-full ${TONE_DOT[scenario.tone]}`} />
            {scenario.label}
            <kbd className="t-fine hidden text-ink-48 lg:inline">{i + 1}</kbd>
          </button>
        ))}
      </div>
    </div>
  );
}
