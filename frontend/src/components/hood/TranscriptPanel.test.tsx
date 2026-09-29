import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Clause, DeviceSnapshot, QueryPlan } from "../../types/generated";
import { initialData, useStore } from "../../lib/store";
import { TranscriptPanel } from "./TranscriptPanel";

const dryer: DeviceSnapshot = {
  info: { device_id: "dryer-01", kind: "dryer", model_id: "DV90T", family: "dryer", display_name: "Dryer", aliases: [] },
  attributes: {},
  revision: 1,
  updated_at: "2026-01-01T00:00:00Z",
};

const status = (device: string): Clause => ({
  clause_id: `status:${device}:-`, device_id: device, intent: "status", error_code: null, params: {},
  stable: true, first_seen_ms: 0, origin: "user",
});

const plan = (clauses: Clause[]): QueryPlan => ({
  plan_id: "P2", revision: 4, label: "Dryer: status", created_at: "", clauses, tasks: [],
});

const heard = (text: string, mentions: string[]) => ({
  utterance_id: "U2", text, final: true, clauses: [], spans: [], is_correction: true, mentions,
});

describe("what it understood (F6)", () => {
  it("shows the question carried over when a correction only names a device", () => {
    act(() =>
      useStore.setState({
        ...initialData,
        devices: { "dryer-01": dryer },
        transcript: heard("wait I meant the dryer", ["dryer-01"]),
        plan: plan([status("dryer-01")]),
      }),
    );
    render(<TranscriptPanel />);
    expect(screen.getByText(/Dryer · status/)).toBeInTheDocument();
    expect(screen.getByText("carried over")).toBeInTheDocument();
    expect(screen.queryByText(/Start a sentence/)).not.toBeInTheDocument();
  });

  it("waits for the device while a correction is still being said", () => {
    act(() => useStore.setState({ ...initialData, transcript: heard("wait I meant the", []), plan: plan([status("washer-01")]) }));
    render(<TranscriptPanel />);
    expect(screen.getByText(/Listening for what you meant/)).toBeInTheDocument();
    expect(screen.queryByText("carried over")).not.toBeInTheDocument();
  });
});
