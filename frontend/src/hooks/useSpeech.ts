import { useEffect } from "react";
import { useStore } from "../lib/store";
import { socket } from "../lib/ws";

/** What the voice is saying right now. The microphone's echo guard compares against it. */
export const speaking = { text: "" };

const PREFERRED_VOICES = ["Samantha", "Google US English", "Microsoft Aria", "Microsoft Jenny", "Karen"];

function pickVoice(): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices();
  for (const name of PREFERRED_VOICES) {
    const match = voices.find((v) => v.name.includes(name));
    if (match) return match;
  }
  return voices.find((v) => v.lang.startsWith("en")) ?? null;
}

export function stopSpeaking(): void {
  speaking.text = "";
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}

/** F19: speaks what the server says, and goes silent the instant it (or the user) says stop. */
export function useSpeech(): void {
  const speech = useStore((s) => s.speech);
  const stopSignal = useStore((s) => s.stopSpeech);
  const voiceOn = useStore((s) => s.voiceOn);

  useEffect(() => {
    if (stopSignal > 0) stopSpeaking();
  }, [stopSignal]);

  useEffect(() => {
    if (!voiceOn) stopSpeaking();
  }, [voiceOn]);

  useEffect(() => {
    if (!speech || !voiceOn || !("speechSynthesis" in window)) return;
    const utterance = new SpeechSynthesisUtterance(speech.text);
    utterance.voice = pickVoice();
    utterance.rate = 1.04;
    utterance.onend = () => {
      if (speaking.text !== speech.text) return;
      speaking.text = "";
      socket.send({ type: "speech.done", data: {} });
    };
    if (speech.priority === "normal") window.speechSynthesis.cancel();
    speaking.text = speech.text;
    window.speechSynthesis.speak(utterance);
  }, [speech, voiceOn]);
}
