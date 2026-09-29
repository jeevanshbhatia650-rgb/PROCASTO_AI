import { describe, expect, it } from "vitest";
import type { RetrievalTask, TimelineEvent } from "../types/generated";
import { buildWaterfall, utterances } from "./waterfall";

const ev = (t_ms: number, kind: TimelineEvent["kind"], detail: Record<string, unknown>): TimelineEvent => ({ t_ms, kind, detail });
const task = (id: string, start: number, end: number | null, status: RetrievalTask["status"] = "done"): RetrievalTask => ({
  task_id: id, clause_id: "c", kind: "live_state", device_id: "washer-01", query: "status", plan_revision: 1,
  depends_on_device_rev: null, status, started_ms: start, finished_ms: end, note: null,
});

const timeline: TimelineEvent[] = [
  ev(1000, "transcript", { utterance_id: "U1", text: "how long", final: false }),
  ev(1300, "transcript", { utterance_id: "U1", text: "how long until the washer", final: false }),
  ev(1600, "transcript", { utterance_id: "U1", text: "how long until the washer finishes", final: false }),
  ev(1600, "clause", { device_id: "washer-01", intent: "status", error_code: null, origin: "user" }),
  ev(2100, "device_event", { device_id: "washer-01", attribute: "state", old: "RUNNING", new: "ERROR" }),
  ev(3000, "transcript", { utterance_id: "U1", text: "how long until the washer finishes", final: true }),
  ev(5000, "transcript", { utterance_id: "U2", text: "wait", final: false }),
];
const names = { "washer-01": "Washer" };

describe("waterfall (F20)", () => {
  it("groups transcript events into utterances", () => {
    expect(utterances(timeline)).toEqual([
      { id: "U1", text: "how long until the washer finishes", start: 1000, end: 3000 },
      { id: "U2", text: "wait", start: 5000, end: null },
    ]);
  });

  it("places each new word at the moment it arrived", () => {
    const [u1, u2] = utterances(timeline);
    const w = buildWaterfall(timeline, {}, u1!, u2, 9000, names);
    expect(w.words.map((x) => [x.text, x.t])).toEqual([
      ["how", 1000], ["long", 1000], ["until", 1300], ["the", 1300], ["washer", 1300], ["finishes", 1600],
    ]);
  });

  it("measures the head start from the first retrieval before the end of speech", () => {
    const [u1, u2] = utterances(timeline);
    const tasks = { T1: task("T1", 1600, 1601), T2: task("T2", 2100, 2102), T9: task("T9", 5200, 5201) };
    const w = buildWaterfall(timeline, tasks, u1!, u2, 9000, names);
    expect(w.leadMs).toBe(1400);
    expect(w.bars.map((b) => b.id)).toEqual(["T1", "T2"]); // the next utterance's work stays out
    expect(w.events).toEqual([{ t: 2100, label: "Washer → error", tone: "bad" }]);
    expect(w.clauses[0]?.label).toBe("washer · status");
  });

  it("a live utterance runs to now", () => {
    const [, u2] = utterances(timeline);
    const w = buildWaterfall(timeline, { T3: task("T3", 5100, null, "running") }, u2!, undefined, 6000, names);
    expect(w.spokeEnd).toBeNull();
    expect(w.bars[0]?.end).toBe(6000);
    expect(w.end).toBeGreaterThan(6000);
  });
});
