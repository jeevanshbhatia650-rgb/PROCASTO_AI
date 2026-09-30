import type { ScenarioId } from "./protocol";
import { useStore } from "./store";
import { socket } from "./ws";

export type { ScenarioId };

export const SCENARIOS: { id: ScenarioId; label: string; tone: "bad" | "warn" | "ok" | "neutral" }[] = [
  { id: "washer_e3", label: "Washer E3", tone: "bad" },
  { id: "washer_done", label: "Washer done", tone: "ok" },
  { id: "ac_spike", label: "AC power spike", tone: "warn" },
  { id: "dryer_done", label: "Dryer done", tone: "ok" },
  { id: "reset", label: "Reset", tone: "neutral" },
];

/** F2: break something in your own demo home. It travels over your socket, so it can't reach anyone else's. */
export function triggerScenario(scenario: ScenarioId): void {
  if (!socket.send({ type: "sim.trigger", data: { scenario } })) {
    useStore.getState().showToast("Not connected yet. Try again in a second.");
  }
}
