import { describe, expect, it } from "vitest";
import { safeNext } from "../pages/auth/AuthLayout";
import { initials } from "../pages/app/shell";
import { askLink, questionFor } from "../pages/app/home/questions";
import type { DeviceSnapshot } from "../types/generated";
import { friendlyError, validateEmail, validatePassword } from "./account";
import { smartthingsResult } from "./connections";
import { alertKey, alertText, deviceView, needsAttention, spokenName } from "./deviceView";
import { initialData, MAX_POWER_SAMPLES, reduce, withPowerSample, type Data } from "./store";

const device = (kind: "washer" | "dryer" | "ac", attributes: Record<string, unknown>): DeviceSnapshot => ({
  info: { device_id: `${kind}-01`, kind, model_id: "M", family: kind, display_name: kind === "ac" ? "AC" : kind[0]!.toUpperCase() + kind.slice(1), aliases: [], room: "Home" },
  attributes,
  revision: 1,
  updated_at: "2026-01-01T00:00:00Z",
});

describe("sign-in redirects", () => {
  it("only ever continues to a page inside the app", () => {
    expect(safeNext("/app/profile")).toBe("/app/profile");
    expect(safeNext(null)).toBe("/app");
    for (const hostile of ["https://evil.example", "//evil.example", "/\\evil.example", "/login", "javascript:alert(1)"]) {
      expect(safeNext(hostile)).toBe("/app");
    }
    expect(safeNext("/app\\@evil.example")).toBe("/app");
  });
});

describe("account input", () => {
  it("checks emails and passwords before anything is sent", () => {
    expect(validateEmail("person@example.com")).toBeNull();
    expect(validateEmail("not-an-email")).not.toBeNull();
    expect(validatePassword("12345678")).toBeNull();
    expect(validatePassword("short")).toMatch(/8 characters/);
  });

  it("turns server errors into sentences people can act on", () => {
    expect(friendlyError(new Error("Invalid login credentials"))).toMatch(/don't match/);
    expect(friendlyError(new Error("email rate limit exceeded"))).toMatch(/Wait a minute/);
    expect(friendlyError(new Error("Something unusual"))).toBe("Something unusual");
    expect(friendlyError(undefined)).toMatch(/Try again/);
  });
});

describe("the dashboard", () => {
  it("asks the most useful question about each device", () => {
    expect(questionFor(device("washer", { error_code: "E3" }))).toBe("What does E3 mean on the washer?");
    expect(questionFor(device("washer", { state: "RUNNING" }))).toBe("How long until the washer finishes?");
    expect(questionFor(device("dryer", { state: "IDLE" }))).toBe("Is the dryer done?");
    expect(questionFor(device("ac", { power_w: 3200 }))).toBe("Why is the AC using so much power?");
    expect(askLink("/demo", "Is the dryer done?")).toBe("/demo/assistant?ask=Is%20the%20dryer%20done%3F");
  });

  it("flags faults and power spikes, not normal running", () => {
    expect(needsAttention(device("washer", { error_code: "E3" }))).toBe(true);
    expect(needsAttention(device("ac", { state: "COOLING", power_w: 3200 }))).toBe(true);
    expect(needsAttention(device("ac", { state: "COOLING", power_w: 1800 }))).toBe(false);
    expect(deviceView(device("washer", { state: "RUNNING", remaining_min: 14, power_w: 450 })).value).toBe("14 min");
  });

  it("shows initials", () => {
    expect(initials("Neha Podder", "x@example.com")).toBe("NP");
    expect(initials("", "sam.lee@example.com")).toBe("SL");
  });
});

describe("device words", () => {
  it("keeps acronyms when a name is used mid-sentence", () => {
    expect(spokenName("Washer")).toBe("washer");
    expect(spokenName("AC")).toBe("AC");
    expect(spokenName("Living Room TV")).toBe("living room TV");
  });

  it("alerts on a new state or fault, never on a new reading", () => {
    const running = device("washer", { state: "RUNNING", power_w: 450, remaining_min: 14 });
    expect(alertKey(running)).toBe(alertKey(device("washer", { state: "RUNNING", power_w: 470, remaining_min: 9 })));
    expect(alertKey(running)).not.toBe(alertKey(device("washer", { state: "DONE" })));
    expect(alertText(device("washer", { state: "RUNNING", error_code: "E3" }))).toBe("Washer stopped · error E3");
    expect(alertText(device("washer", { state: "DONE" }))).toBe("Washer finished");
    expect(alertText(device("ac", { state: "COOLING", power_w: 3200 }))).toBe("AC is drawing unusually high power");
  });
});

describe("coming back from Samsung", () => {
  it("explains known results and ignores anything else in the address", () => {
    expect(smartthingsResult("connected")?.ok).toBe(true);
    expect(smartthingsResult("failed")?.message).toMatch(/Samsung didn't respond/);
    expect(smartthingsResult("toString")).toBeNull(); // not an inherited property
    expect(smartthingsResult(null)).toBeNull();
  });
});

describe("store", () => {
  const snapshot = (watts: number) => [device("washer", { power_w: watts }), device("ac", { power_w: 1000 })];

  it("keeps a fixed window of whole-home power samples", () => {
    const home = (watts: number) => Object.fromEntries(snapshot(watts).map((d) => [d.info.device_id, d]));
    let power: number[] = [];
    for (let i = 0; i < MAX_POWER_SAMPLES + 5; i++) power = withPowerSample(power, home(i));
    expect(power).toHaveLength(MAX_POWER_SAMPLES);
    expect(power.at(-1)).toBe(1000 + MAX_POWER_SAMPLES + 4); // the newest reading, AC included
    expect(power[0]).toBe(1005); // the five oldest fell off
  });

  it("starts clean when a new session says hello, clearing the previous home's devices", () => {
    let state: Data = { ...initialData, ...reduce(initialData, { type: "devices.snapshot", data: snapshot(400) }, 1) };
    state = { ...state, cards: { a: {} as never }, turns: [{ id: "U1", text: "hi" }] };
    const hello = { session_id: "s", home: "demo" as const, signed_in: false, notice: "", llm: "templates", dense_model: null };
    const next = { ...state, ...reduce(state, { type: "hello", data: hello }, 2) };
    expect(next.cards).toEqual({});
    expect(next.turns).toEqual([]);
    expect(Object.keys(next.devices)).toHaveLength(0);
    expect(next.hello?.home).toBe("demo");
  });
});
