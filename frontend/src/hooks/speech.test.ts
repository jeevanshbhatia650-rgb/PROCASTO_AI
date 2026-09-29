import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useStore } from "../lib/store";
import { speaking, useSpeech } from "./useSpeech";
import { isEcho } from "./useSpeechInput";

class FakeUtterance {
  text: string;
  voice: unknown = null;
  rate = 1;
  onend: (() => void) | null = null;
  constructor(text: string) {
    this.text = text;
  }
}

describe("useSpeech (F19)", () => {
  const synth = { speak: vi.fn(), cancel: vi.fn(), getVoices: () => [] };

  beforeEach(() => {
    vi.stubGlobal("speechSynthesis", synth);
    vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
    synth.speak.mockClear();
    synth.cancel.mockClear();
    useStore.setState({ speech: null, stopSpeech: 0, voiceOn: true });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("speaks what the server says", () => {
    renderHook(() => useSpeech());
    act(() => useStore.getState().apply({ type: "speech.say", data: { text: "The washer is done.", card_id: "c", priority: "normal" } }));
    expect(synth.speak).toHaveBeenCalledTimes(1);
    expect(speaking.text).toBe("The washer is done.");
  });

  it("goes silent the moment a stop arrives", () => {
    renderHook(() => useSpeech());
    act(() => useStore.getState().apply({ type: "speech.say", data: { text: "E3 means…", card_id: "c", priority: "normal" } }));
    synth.cancel.mockClear();
    act(() => useStore.getState().apply({ type: "speech.stop", data: {} }));
    expect(synth.cancel).toHaveBeenCalled();
    expect(speaking.text).toBe("");
  });

  it("stays quiet when voice replies are muted", () => {
    useStore.setState({ voiceOn: false });
    renderHook(() => useSpeech());
    act(() => useStore.getState().apply({ type: "speech.say", data: { text: "hello", card_id: "c", priority: "normal" } }));
    expect(synth.speak).not.toHaveBeenCalled();
  });
});

describe("echo guard", () => {
  it("ignores the mic hearing our own voice", () => {
    expect(isEcho("the washer stopped", "The washer stopped with error E3.")).toBe(true);
  });
  it("treats new words as the user barging in", () => {
    expect(isEcho("wait I meant the dryer", "The washer stopped with error E3.")).toBe(false);
  });
  it("never flags speech when nothing is playing", () => {
    expect(isEcho("the washer", "")).toBe(false);
  });
});
