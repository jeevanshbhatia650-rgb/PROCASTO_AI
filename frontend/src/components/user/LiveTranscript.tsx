import type { Span } from "../../types/generated";
import { useStore } from "../../lib/store";

const ROLE_CLASS: Record<Span["role"], string> = {
  device: "text-primary",
  intent: "text-run-text",
  code: "text-bad-text",
  correction: "text-ink-48 italic",
  pronoun: "text-primary underline decoration-dotted underline-offset-4",
};

function highlight(text: string, spans: Span[]) {
  const parts: { text: string; role?: Span["role"] }[] = [];
  let cursor = 0;
  for (const span of spans) {
    if (span.start > cursor) parts.push({ text: text.slice(cursor, span.start) });
    parts.push({ text: text.slice(span.start, span.end), role: span.role });
    cursor = span.end;
  }
  if (cursor < text.length) parts.push({ text: text.slice(cursor) });
  return parts;
}

/** Under the hood only: the sentence as it streams in, with the words the engine understood coloured by role. */
export function LiveTranscript() {
  const transcript = useStore((s) => s.transcript);
  const text = transcript?.text ?? "";
  const listening = transcript !== null && !transcript.final;

  if (!text) return <p className="t-caption text-ink-48">Nothing heard yet. Talk or type on the left.</p>;
  return (
    <p className="t-tagline text-balance">
      {highlight(text, transcript?.spans ?? []).map((part, i) =>
        part.role ? (
          <span key={i} className={ROLE_CLASS[part.role]}>
            {part.text}
          </span>
        ) : (
          <span key={i}>{part.text}</span>
        ),
      )}
      {listening && <span className="caret ml-1 inline-block h-[0.9em] w-[3px] translate-y-[0.12em] rounded-full bg-primary" />}
    </p>
  );
}
