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
      <div className="mt-6 flex items-center gap-3">
        <button
          type="button"
          onClick={toggleMic}
          disabled={!voice.supported}
          aria-pressed={voice.listening}
          aria-label={voice.listening ? "Stop listening" : "Start listening"}
          title={voice.supported ? "Click, or hold Space, to talk" : "Voice needs Chrome or Edge. Typing streams the same way."}
          className="pressable relative grid h-14 w-14 shrink-0 place-items-center rounded-full bg-primary text-white transition-[background-color,transform] duration-150 disabled:bg-chip disabled:text-ink-48"
        >
          {voice.listening && <span className="listening-ring absolute inset-0 rounded-full bg-primary" />}
          <MicIcon size={24} className="relative" />
        </button>
        <form onSubmit={onSubmit} className="min-w-0 flex-1">
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
        </form>
      </div>
      <p className="mt-2 hidden pl-[68px] t-fine text-ink-48 sm:block">
        Every word streams to the engine as you talk or type. Hold Space to talk, press R for the 20-second demo.
      </p>
    </>
  );
}
