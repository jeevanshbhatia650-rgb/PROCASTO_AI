import { AnimatePresence, motion } from "motion/react";
import { useNow } from "../../hooks/useNow";
import { useStore } from "../../lib/store";
import type { AnswerCard as Card } from "../../types/generated";
import { AnswerCard } from "./AnswerCard";
import { ParkedStack } from "./ParkedStack";

const TYPE_ORDER: Card["type"][] = ["status", "problem", "action", "info", "confirm"];
const EASE_OUT = [0.23, 1, 0.32, 1] as const;
const STAGGER_S = 0.05;

/** F17: the answer, card by card, each with its sources. */
export function AnswerCards() {
  const plan = useStore((s) => s.plan);
  const cards = useStore((s) => s.cards);
  const now = useNow();
  const deviceOrder = plan ? [...new Set(plan.clauses.map((c) => c.device_id ?? ""))] : [];
  const active = plan
    ? Object.values(cards)
        .filter((c) => c.plan_id === plan.plan_id)
        .sort(
          (a, b) =>
            deviceOrder.indexOf(a.device_id ?? "") - deviceOrder.indexOf(b.device_id ?? "") ||
            TYPE_ORDER.indexOf(a.type) - TYPE_ORDER.indexOf(b.type),
        )
    : [];

  return (
    <section aria-label="Answers" className="mt-10">
      <div className="mb-3 flex items-baseline gap-3">
        <h2 className="t-section">Answer</h2>
        {plan && <span className="t-caption text-ink-48">{plan.label}</span>}
      </div>
      {active.length === 0 && (
        <div className="rounded-lg border border-dashed border-black/10 px-5 py-8 text-center t-caption text-ink-48">
          Answers appear here as they’re found, each with the source it came from.
        </div>
      )}
      <div className="space-y-3" aria-live="polite">
        <AnimatePresence initial={false} mode="popLayout">
          {active.map((card, i) => (
            <motion.div
              key={card.card_id}
              layout="position"
              initial={{ opacity: 0, transform: "translateY(10px) scale(0.98)" }}
              animate={{ opacity: 1, transform: "translateY(0px) scale(1)" }}
              exit={{ opacity: 0, transform: "translateY(12px) scale(0.98)", transition: { duration: 0.16, ease: EASE_OUT } }}
              transition={{ duration: 0.26, ease: EASE_OUT, delay: i * STAGGER_S, layout: { type: "spring", bounce: 0, duration: 0.35 } }}
            >
              <AnswerCard card={card} now={now} />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      <ParkedStack />
    </section>
  );
}
