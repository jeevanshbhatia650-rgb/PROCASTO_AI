import { Keyboard, Send } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import type { VoiceInput as Voice } from "../../hooks/useSpeechInput";
import { sendTranscript } from "../../lib/ws";
import { MicIcon } from "../icons";

interface VoiceInputProps {
  voice: Voice;
  draft: string;
  onDraft: (text: string) => void;
}

/** F5: talk (Web Speech interim results) or type; either way every new word streams to the engine. */
export function VoiceInput({ voice, draft, onDraft }: VoiceInputProps) {
  const lastSent = useRef("");
  const [focused, setFocused] = useState(false);
  const [typing, setTyping] = useState(false);

  const onChange = (value: string) => {
    onDraft(value);
    const words = value.trim();
    if (value.endsWith(" ") && words && words !== lastSent.current) {
      lastSent.current = words;
      sendTranscript(words, false);
    }
  };
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    sendTranscript(text, true);
    lastSent.current = "";
    onDraft("");
  };
  const toggleMic = () => (voice.listening ? voice.stop() : voice.start());

  return (
    <>
      <div className="mt-7 flex flex-col items-center gap-3">
        <button
          id="voice-button"
          type="button"
          onClick={toggleMic}
          disabled={!voice.supported}
          aria-pressed={voice.listening}
          aria-label="Talk"
          title={voice.supported ? "Click, or hold Space, to talk" : "Voice needs Chrome or Edge. Typing streams the same way."}
          className="pressable relative grid h-20 w-20 shrink-0 place-items-center rounded-full bg-ink text-white shadow-lg transition-[background-color,transform] duration-150 disabled:bg-chip disabled:text-ink-48"
        >
          {voice.listening && <span className="listening-ring absolute inset-0 rounded-full bg-primary" />}
          <MicIcon size={32} className="relative" />
        </button>
        <p className="t-fine text-ink-48">{voice.listening ? "Tap to finish" : voice.supported ? "Tap to talk · hold Space" : "Voice is unavailable in this browser"}</p>
        <button type="button" onClick={() => setTyping((open) => !open)} aria-expanded={typing} className="pressable inline-flex items-center gap-2 rounded-full px-4 py-2 t-caption text-ink-80 hover:bg-white/70"><Keyboard size={16} aria-hidden="true" /> {typing ? "Hide typing" : "Type instead"}</button>
        {typing && <form onSubmit={onSubmit} className="mx-auto flex w-full max-w-[640px] items-center gap-2">
          <label htmlFor="ask" className="sr-only">
            Ask about your home
          </label>
          <input
            id="ask"
            value={draft}
            onChange={(e) => onChange(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            autoComplete="off"
            placeholder={voice.listening ? "Listening…" : "Type a question…"}
            className={`h-12 w-full rounded-full border bg-canvas px-5 t-body outline-none transition-[border-color,box-shadow] duration-150 placeholder:text-ink-48 ${
              focused ? "border-primary-focus shadow-[0_0_0_4px_rgba(0,113,227,0.14)]" : "border-black/[0.08]"
            }`}
          />
          <button type="submit" className="pressable grid h-11 w-11 shrink-0 place-items-center rounded-full bg-ink text-white" aria-label="Send question"><Send size={17} aria-hidden="true" /></button>
        </form>}
      </div>
    </>
  );
}
