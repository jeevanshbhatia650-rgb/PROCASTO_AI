import { useStore } from "./store";

export type ScenarioId = "washer_e3" | "washer_done" | "ac_spike" | "dryer_done" | "reset";

export const SCENARIOS: { id: ScenarioId; label: string; tone: "bad" | "warn" | "ok" | "neutral" }[] = [
  { id: "washer_e3", label: "Washer E3", tone: "bad" },
  { id: "washer_done", label: "Washer done", tone: "ok" },
  { id: "ac_spike", label: "AC power spike", tone: "warn" },
  { id: "dryer_done", label: "Dryer done", tone: "ok" },
  { id: "reset", label: "Reset", tone: "neutral" },
];

/** F2: the break-something panel. */
export async function triggerScenario(scenario: ScenarioId): Promise<void> {
  try {
    const response = await fetch("/api/sim/trigger", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ scenario }),
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => ({}))) as { detail?: string };
      useStore.getState().showToast(body.detail ?? "That didn't work. Is the backend running?");
    }
  } catch {
    useStore.getState().showToast("Can't reach the backend. Start it with `make dev-back`.");
  }
}
