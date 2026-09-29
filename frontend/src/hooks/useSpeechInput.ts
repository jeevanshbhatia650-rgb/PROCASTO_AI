import { useCallback, useRef, useState } from "react";
import { useStore } from "../lib/store";
import { sendTranscript, socket } from "../lib/ws";
import { speaking, stopSpeaking } from "./useSpeech";

type Alternative = { transcript: string };
type Result = { isFinal: boolean; 0: Alternative };
type ResultEvent = { resultIndex: number; results: ArrayLike<Result> };
type Recognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: ResultEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type RecognitionCtor = new () => Recognition;

const ECHO_OVERLAP = 0.7;

function recognitionCtor(): RecognitionCtor | undefined {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

/** True when the mic is most likely hearing our own voice through the speakers. */
export function isEcho(heard: string, spoken: string): boolean {
  if (!spoken) return false;
  const said = new Set(spoken.toLowerCase().match(/[a-z0-9]+/g) ?? []);
  const words = heard.toLowerCase().match(/[a-z0-9]+/g) ?? [];
  if (words.length === 0) return true;
  return words.filter((w) => said.has(w)).length / words.length >= ECHO_OVERLAP;
}

export type VoiceInput = { supported: boolean; listening: boolean; start: () => void; stop: () => void };

/** F5 + F19: Web Speech interim results stream as partial transcripts; talking over the voice barges in. */
export function useSpeechInput(): VoiceInput {
  const [listening, setListening] = useState(false);
  const recognition = useRef<Recognition | null>(null);
  const Ctor = recognitionCtor();

  const start = useCallback(() => {
    if (!Ctor || recognition.current) return;
    const rec = new Ctor();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-US";
    let interim = "";
    rec.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const text = result?.[0].transcript.trim() ?? "";
        if (!result || !text || isEcho(text, speaking.text)) continue;
        if (speaking.text) {
          stopSpeaking(); // local silence first, same frame
          socket.send({ type: "speech.barge_in", data: {} });
        }
        if (result.isFinal) {
          sendTranscript(text, true);
          interim = "";
        } else if (text !== interim) {
          sendTranscript(text, false);
          interim = text;
        }
      }
    };
    rec.onerror = (event) => {
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        useStore.getState().showToast("Microphone is blocked. Allow it in the browser, or type your question.");
      } else if (event.error === "network") {
        useStore.getState().showToast("Speech recognition needs an internet connection. Type instead, or press Replay.");
      }
    };
    rec.onend = () => {
      if (interim) sendTranscript(interim, true); // released mid-sentence: what we heard is the question
      recognition.current = null;
      setListening(false);
    };
    rec.start();
    recognition.current = rec;
    setListening(true);
  }, [Ctor]);

  const stop = useCallback(() => recognition.current?.stop(), []);

  return { supported: Boolean(Ctor), listening, start, stop };
}
