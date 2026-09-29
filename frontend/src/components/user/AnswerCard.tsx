import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import type { AnswerCard as Card } from "../../types/generated";
import { ConfirmDialog } from "./ConfirmDialog";
import { SourceChip } from "./SourceChip";

const TYPE_LABEL: Record<Card["type"], string> = {
  status: "Status",
  problem: "Problem",
  action: "What to do",
  info: "Energy",
  confirm: "Needs your OK",
};

const SEVERITY_DOT: Record<Card["severity"], string> = {
  ok: "bg-ok",
  info: "bg-off",
  warn: "bg-run",
  error: "bg-bad",
};

/** Plays the attention ring once when a card turns into an error by itself. */
function useEscalated(severity: Card["severity"]): number {
  const previous = useRef(severity);
  const [pulse, setPulse] = useState(0);
  useEffect(() => {
    if (severity === "error" && previous.current !== "error") setPulse((n) => n + 1);
    previous.current = severity;
  }, [severity]);
  return pulse;
}

export function AnswerCard({ card, now }: { card: Card; now: number }) {
  const pulse = useEscalated(card.severity);
  return (
    <article key={pulse} className={`card p-5 ${pulse ? "changed-ring" : ""}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${SEVERITY_DOT[card.severity]}`} />
        <span className="t-eyebrow text-ink-48">{TYPE_LABEL[card.type]}</span>
        <div className="ml-auto flex flex-wrap justify-end gap-1.5">
          {card.sources.map((source) => (
            <SourceChip key={`${source.kind}-${source.label}`} source={source} now={now} />
          ))}
        </div>
      </div>
      {/* Re-keyed on content change: the new words blur in, masking the swap (answers rewrite themselves). */}
      <motion.div
        key={`${card.title}|${card.body}`}
        initial={{ opacity: 0, filter: "blur(2px)" }}
        animate={{ opacity: 1, filter: "blur(0px)" }}
        transition={{ duration: 0.2, ease: "easeOut" }}
      >
        <h3 className="t-tagline mt-2.5">{card.title}</h3>
        {card.body && <p className="t-body mt-1.5 text-ink-80">{card.body}</p>}
      </motion.div>
      {card.steps.length > 0 && (
        <ol className="mt-3.5 space-y-2">
          {card.steps.map((step, i) => (
            <li key={step} className="flex gap-3 t-caption text-ink-80">
              <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-parchment t-fine font-semibold text-ink">
                {i + 1}
              </span>
              <span className="pt-px">{step}</span>
            </li>
          ))}
        </ol>
      )}
      <ConfirmDialog key={card.command ? card.command.label : "none"} card={card} />
    </article>
  );
}
