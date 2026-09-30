import { AnimatePresence, motion } from "motion/react";
import { useNow } from "../../hooks/useNow";
import { useStore } from "../../lib/store";

const EASE_OUT = [0.23, 1, 0.32, 1] as const;
const SHOWN = 8;
const THINKING_MS = 15_000; // after this a reply isn't coming (a cancel, or nothing to say)

/** "gemini-3.1-flash-lite" -> "Gemini 3.1 flash lite"; the cards' own words say so plainly. */
export function modelLabel(model: string): string {
  if (model === "templates") return "from the answer cards";
  return model
    .replace(/^gemini-/, "Gemini ")
    .replace(/^gemma-/, "Gemma ")
    .replace(/-it$/, "")
    .replace(/-/g, " ");
}

/** The one-to-one conversation: what you said, what PROCASTO said back, and which model said it. */
export function Conversation() {
  const chat = useStore((s) => s.chat);
  const now = useNow();
  const last = chat.at(-1);
  if (!last) return null;
  const thinking = last.role === "you" && now - last.at < THINKING_MS;

  return (
    <section aria-label="Conversation" className="mx-auto mb-8 max-w-2xl">
      <ol className="space-y-2.5" aria-live="polite">
        <AnimatePresence initial={false}>
          {chat.slice(-SHOWN).map((line) => (
            <motion.li
              key={line.id}
              layout="position"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.24, ease: EASE_OUT }}
              className={line.role === "you" ? "flex justify-end" : "flex justify-start"}
            >
              {line.role === "you" ? (
                <p className="t-caption max-w-[80%] rounded-2xl rounded-br-md bg-ink px-4 py-2.5 text-white">
                  <span className="sr-only">You: </span>
                  {line.text}
                </p>
              ) : (
                <div className="card max-w-[85%] rounded-2xl rounded-bl-md px-4 py-3">
                  <p className="t-body text-ink">
                    <span className="sr-only">PROCASTO: </span>
                    {line.text}
                  </p>
                  {line.model && <p className="t-fine mt-1.5 text-ink-48">via {modelLabel(line.model)}</p>}
                </div>
              )}
            </motion.li>
          ))}
          {thinking && (
            <motion.li
              key="thinking"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex justify-start"
            >
              <div className="card flex items-center gap-1.5 rounded-2xl rounded-bl-md px-4 py-3.5" role="status">
                <span className="sr-only">PROCASTO is thinking</span>
                {[0, 1, 2].map((i) => (
                  <motion.span
                    key={i}
                    aria-hidden="true"
                    className="h-1.5 w-1.5 rounded-full bg-ink-48"
                    animate={{ opacity: [0.25, 1, 0.25] }}
                    transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.18 }}
                  />
                ))}
              </div>
            </motion.li>
          )}
        </AnimatePresence>
      </ol>
    </section>
  );
}
