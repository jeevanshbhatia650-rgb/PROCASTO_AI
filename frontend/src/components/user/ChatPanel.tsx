import { useCallback, useEffect, useRef, useState } from "react";
import type { VoiceInput as Voice } from "../../hooks/useSpeechInput";
import { useStore } from "../../lib/store";
import { typeOut } from "../../lib/typing";
import { Suggestions } from "./Suggestions";
import { VoiceInput } from "./VoiceInput";

function statusLine(listening: boolean, final: boolean | undefined, correction: boolean | undefined): string {
  if (listening) return "Listening";
  if (correction) return "Correction heard";
  if (final === false) return "Hearing you";
  if (final) return "You asked";
  return "Ask your home";
}

type Props = {
  voice: Voice;
  question?: string | null; // asked once the session is ready, e.g. "Ask why" on the dashboard
  onAsked?: () => void;
};

export function ChatPanel({ voice, question, onAsked }: Props) {
  const [draft, setDraft] = useState("");
  const transcript = useStore((s) => s.transcript);
  const ready = useStore((s) => s.connection === "open" && s.hello !== null);
  const cancelTyping = useRef<(() => void) | null>(null);

  useEffect(() => () => cancelTyping.current?.(), []);

  const ask = useCallback((text: string) => {
    cancelTyping.current?.();
    cancelTyping.current = typeOut(text, setDraft);
  }, []);

  useEffect(() => {
    if (!question || !ready) return;
    ask(question);
    onAsked?.();
  }, [question, ready, ask, onAsked]);
  return (
    <section aria-label="Ask" className="pb-8 pt-7 text-center sm:pt-12">
      <p className="t-eyebrow mb-3 text-ink-48" role="status">
        {statusLine(voice.listening, transcript?.final, transcript?.is_correction)}
      </p>
      <h2 className="t-display">{voice.listening ? "I'm listening" : "What would you like to know?"}</h2>
      <p className="t-caption mt-2 text-ink-48">Ask naturally. Your devices and answers stay below.</p>
      <VoiceInput voice={voice} draft={draft} onDraft={setDraft} />
      <Suggestions onAsk={ask} />
    </section>
  );
}
