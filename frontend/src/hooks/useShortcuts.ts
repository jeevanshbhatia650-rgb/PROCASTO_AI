import { useEffect } from "react";
import { useStore } from "../lib/store";
import { socket } from "../lib/ws";
import { useShell } from "../pages/app/shell";
import type { VoiceInput } from "./useSpeechInput";

const PRESSED_BY_SPACE = "button, a[href], summary, select, [role=button], [role=switch], [role=checkbox], [role=tab], [role=menuitem]";

function typing(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
}

/** Space already presses a focused button or switch; stealing it would lock keyboard users out. */
function spaceBelongsTo(target: EventTarget | null): boolean {
  return typing(target) || (target instanceof Element && target.matches(PRESSED_BY_SPACE));
}

/** On the assistant: Space = hold to talk, H = under the hood, R = replay. (1-5 live in the app shell.) */
export function useShortcuts(voice: VoiceInput): void {
  const { mode } = useShell();
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (typing(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.code === "Space") {
        if (spaceBelongsTo(e.target)) return;
        e.preventDefault();
        if (!e.repeat) voice.start();
      } else if (mode === "demo" && (e.key === "h" || e.key === "H")) {
        const { hoodOpen, setHood } = useStore.getState();
        setHood(!hoodOpen);
      } else if (mode === "demo" && (e.key === "r" || e.key === "R")) {
        socket.send({ type: "replay.start", data: { script_id: "main_demo" } });
      }
    };
    const up = (e: KeyboardEvent) => {
      if (e.code === "Space" && !spaceBelongsTo(e.target)) voice.stop();
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [voice, mode]);
}
