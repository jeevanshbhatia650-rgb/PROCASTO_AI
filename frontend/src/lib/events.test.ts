import { describe, expect, it } from "vitest";
import type { DeviceSnapshot, ParkedPlan, TimelineEvent } from "../types/generated";
import { describe as describeEvent } from "./events";
import { formatPower, formatSeconds, timeAgo } from "./format";
import { suggestions } from "./suggestions";

const names = { "washer-01": "Washer", "ac-01": "AC" };
const ev = (kind: TimelineEvent["kind"], detail: Record<string, unknown>): TimelineEvent => ({ t_ms: 4200, kind, detail });

describe("event feed wording", () => {
  it("reads device faults in plain English", () => {
    expect(describeEvent(ev("device_event", { device_id: "washer-01", attribute: "state", old: "RUNNING", new: "ERROR" }), names))
      .toMatchObject({ text: "Washer: running → error", tone: "bad" });
    expect(describeEvent(ev("device_event", { device_id: "washer-01", attribute: "error_code", old: null, new: "E3" }), names)?.text)
      .toBe("Washer reported error E3");
  });

  it("explains invalidations, stale drops, parks and resumes", () => {
    expect(describeEvent(ev("invalidate", { device_id: "washer-01", stale: ["T1"], replaced_by: ["T4"] }), names)?.text)
      .toBe("Washer changed: T1 stale, fetching T4");
    expect(describeEvent(ev("stale_drop", { task_id: "T3" }), names)?.text).toBe("Dropped late result T3 (plan moved on)");
    expect(describeEvent(ev("park", { label: "Washer: status" }), names)?.text).toBe("Parked “Washer: status”");
    expect(describeEvent(ev("resume", { reused: ["T3"], refetched: ["T5"] }), names)?.text).toBe("Resumed: 1 reused · 1 refetched");
  });

  it("skips events the feed doesn't show", () => {
    expect(describeEvent(ev("task_start", { task_id: "T1" }), names)).toBeNull();
    expect(describeEvent(ev("clause", { origin: "user" }), names)).toBeNull();
  });
});

const device = (kind: "washer" | "dryer" | "ac", attributes: Record<string, unknown>): DeviceSnapshot => ({
  info: { device_id: `${kind}-01`, kind, model_id: "M", family: kind, display_name: kind === "ac" ? "AC" : kind[0]!.toUpperCase() + kind.slice(1), aliases: [], room: "Home" },
  attributes, revision: 1, updated_at: "2026-01-01T00:00:00Z",
});

describe("smart suggestions", () => {
  it("offers the error code first when a device faults", () => {
    const out = suggestions([device("washer", { state: "ERROR", error_code: "E3" })], []);
    expect(out[0]).toBe("What does E3 mean on the washer?");
  });

  it("asks about a power spike and offers to resume a parked question", () => {
    const parked: ParkedPlan[] = [{ plan_id: "P1", label: "Washer: status", device_ids: ["washer-01"], task_count: 2 }];
    const out = suggestions([device("washer", { state: "RUNNING" }), device("ac", { power_w: 3200 })], parked);
    expect(out).toEqual(["Why is the AC using so much power?", "Go back to the washer", "How long until the washer finishes?"]);
  });
});

describe("formatting", () => {
  it("formats power, durations and ages", () => {
    expect(formatPower(450)).toBe("450 W");
    expect(formatPower(3200)).toBe("3.2 kW");
    expect(formatSeconds(1400)).toBe("1.4 s");
    expect(formatSeconds(-380)).toBe("380 ms");
    expect(timeAgo("2026-01-01T00:00:00Z", Date.parse("2026-01-01T00:00:07Z"))).toBe("7 s ago");
  });
});
