import { useEffect } from "react";
import { triggerScenario, SCENARIOS } from "../lib/api";
import { useStore } from "../lib/store";
import { socket } from "../lib/ws";
import type { VoiceInput } from "./useSpeechInput";

function typing(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
}

/** Space = hold to talk, H = under the hood, R = replay, 1-5 = break something. */
export function useShortcuts(voice: VoiceInput): void {
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (typing(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.code === "Space") {
        e.preventDefault();
        if (!e.repeat) voice.start();
      } else if (e.key === "h" || e.key === "H") {
        const { hoodOpen, setHood } = useStore.getState();
        setHood(!hoodOpen);
      } else if (e.key === "r" || e.key === "R") {
        socket.send({ type: "replay.start", data: { script_id: "main_demo" } });
      } else {
        const scenario = SCENARIOS[Number(e.key) - 1];
        if (scenario) void triggerScenario(scenario.id);
      }
    };
    const up = (e: KeyboardEvent) => {
      if (e.code === "Space" && !typing(e.target)) voice.stop();
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [voice]);
}
