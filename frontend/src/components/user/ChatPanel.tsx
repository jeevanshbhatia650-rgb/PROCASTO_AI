import { useEffect, useRef, useState } from "react";
import type { VoiceInput as Voice } from "../../hooks/useSpeechInput";
import { useStore } from "../../lib/store";
import { typeOut } from "../../lib/typing";
import { LiveTranscript } from "./LiveTranscript";
import { Suggestions } from "./Suggestions";
import { VoiceInput } from "./VoiceInput";

function statusLine(listening: boolean, final: boolean | undefined, correction: boolean | undefined): string {
  if (listening) return "Listening";
  if (correction) return "Correction heard";
  if (final === false) return "Hearing you";
  if (final) return "You asked";
  return "Ask your home";
}

export function ChatPanel({ voice }: { voice: Voice }) {
  const [draft, setDraft] = useState("");
  const transcript = useStore((s) => s.transcript);
  const turns = useStore((s) => s.turns);
  const cancelTyping = useRef<(() => void) | null>(null);

  useEffect(() => () => cancelTyping.current?.(), []);

  const ask = (question: string) => {
    cancelTyping.current?.();
    cancelTyping.current = typeOut(question, setDraft);
  };
  const earlier = turns.slice(0, -1).slice(-2);

  return (
    <section aria-label="Ask" className="pb-8 pt-10">
      <p className="t-eyebrow mb-3 text-ink-48">
        {statusLine(voice.listening, transcript?.final, transcript?.is_correction)}
      </p>
      <LiveTranscript draft={draft} />
      <VoiceInput voice={voice} draft={draft} onDraft={setDraft} />
      <Suggestions onAsk={ask} />
      {earlier.length > 0 && (
        <p className="mt-4 t-fine text-ink-48">
          Earlier: {earlier.map((t) => `“${t.text}”`).join(" · ")}
        </p>
      )}
    </section>
  );
}
