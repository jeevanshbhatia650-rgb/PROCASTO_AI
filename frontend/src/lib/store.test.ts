import { describe, expect, it } from "vitest";
import type { AnswerCard, DeviceSnapshot, RetrievalTask } from "../types/generated";
import { initialData, reduce, type Data } from "./store";

const snapshot = (id: string, attributes: Record<string, unknown>): DeviceSnapshot => ({
  info: { device_id: id, kind: "washer", model_id: "WW90T", family: "washer", display_name: "Washer", aliases: [] },
  attributes,
  revision: 1,
  updated_at: "2026-01-01T00:00:00Z",
});

const card = (id: string): AnswerCard => ({
  card_id: id, type: "status", device_id: "washer-01", title: "t", body: "b", evidence_ids: [], plan_revision: 1,
  speakable: "s", plan_id: "P1", severity: "ok", steps: [], sources: [], command: null,
});

const task = (n: number): RetrievalTask => ({
  task_id: `T${n}`, clause_id: "c", kind: "live_state", device_id: "washer-01", query: "status", plan_revision: 1,
  depends_on_device_rev: null, status: "done", started_ms: n, finished_ms: n, note: null,
});

const apply = (state: Data, ...messages: Parameters<typeof reduce>[1][]): Data =>
  messages.reduce((s, m) => ({ ...s, ...reduce(s, m, 5000) }), state);

describe("store reducer", () => {
  it("replaces one device on update and keeps the others", () => {
    const s = apply(
      initialData,
      { type: "devices.snapshot", data: [snapshot("washer-01", { state: "RUNNING" }), snapshot("dryer-01", {})] },
      { type: "device.update", data: snapshot("washer-01", { state: "ERROR" }) },
    );
    expect(s.devices["washer-01"]?.attributes.state).toBe("ERROR");
    expect(Object.keys(s.devices)).toHaveLength(2);
  });

  it("upserts and removes cards by id", () => {
    const s = apply(initialData, { type: "card.upsert", data: card("a") }, { type: "card.upsert", data: card("b") }, {
      type: "card.remove",
      data: { card_id: "a" },
    });
    expect(Object.keys(s.cards)).toEqual(["b"]);
  });

  it("a stop order clears speech and bumps the stop signal", () => {
    const s = apply(
      initialData,
      { type: "speech.say", data: { text: "hi", card_id: "a", priority: "normal" } },
      { type: "speech.stop", data: {} },
    );
    expect(s.speech).toBeNull();
    expect(s.stopSpeech).toBe(1);
  });

  it("remembers final utterances as turns, not partials", () => {
    const base = { utterance_id: "U1", clauses: [], spans: [], is_correction: false };
    const s = apply(
      initialData,
      { type: "clauses.update", data: { ...base, text: "is the", final: false } },
      { type: "clauses.update", data: { ...base, text: "is the dryer done", final: true } },
    );
    expect(s.turns).toEqual([{ id: "U1", text: "is the dryer done" }]);
  });

  it("caps tasks and keeps the newest", () => {
    let s = initialData;
    for (let n = 1; n <= 70; n++) s = apply(s, { type: "task.update", data: task(n) });
    expect(Object.keys(s.tasks)).toHaveLength(60);
    expect(s.tasks.T70).toBeDefined();
    expect(s.tasks.T1).toBeUndefined();
  });

  it("tracks the server clock offset from timeline events", () => {
    const s = apply(initialData, { type: "timeline.event", data: { t_ms: 1200, kind: "clause", detail: {} } });
    expect(s.clockOffset).toBe(3800);
  });

  it("session reset clears the conversation but keeps the home", () => {
    const s = apply(
      initialData,
      { type: "devices.snapshot", data: [snapshot("washer-01", {})] },
      { type: "card.upsert", data: card("a") },
      { type: "session.reset", data: {} },
    );
    expect(s.cards).toEqual({});
    expect(Object.keys(s.devices)).toEqual(["washer-01"]);
  });

  it("the demo caption clears when the replay is done", () => {
    const s = apply(
      initialData,
      { type: "demo.step", data: { index: 1, total: 7, text: "hi" } },
      { type: "demo.step", data: { done: true } },
    );
    expect(s.demo).toBeNull();
  });
});
