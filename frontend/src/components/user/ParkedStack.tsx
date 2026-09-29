import { AnimatePresence, motion } from "motion/react";
import { useStore } from "../../lib/store";
import { socket } from "../../lib/ws";
import { PauseIcon } from "../icons";

const EASE_OUT = [0.23, 1, 0.32, 1] as const;

/** F16: a correction parks the old question here instead of throwing it away. */
export function ParkedStack() {
  const parked = useStore((s) => s.parked);
  const cards = useStore((s) => s.cards);
  if (parked.length === 0) return null;
  return (
    <div className="mt-8">
      <p className="t-eyebrow mb-2.5 text-ink-48">Parked</p>
      <div className="space-y-2">
        <AnimatePresence initial={false}>
          {parked.map((plan) => {
            const kept = Object.values(cards).filter((c) => c.plan_id === plan.plan_id).length;
            return (
              <motion.div
                key={plan.plan_id}
                layout
                initial={{ opacity: 0, transform: "translateY(-8px)" }}
                animate={{ opacity: 1, transform: "translateY(0px)" }}
                exit={{ opacity: 0, transform: "translateY(-8px)", transition: { duration: 0.16 } }}
                transition={{ duration: 0.24, ease: EASE_OUT }}
                className="flex items-center gap-3 rounded-lg border border-primary/20 bg-primary/[0.04] px-4 py-3"
              >
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-primary/10 text-primary">
                  <PauseIcon size={16} />
                </span>
                <div className="min-w-0">
                  <p className="t-caption-strong truncate">{plan.label}</p>
                  <p className="t-fine text-ink-48">
                    {kept} answer{kept === 1 ? "" : "s"} kept · fresh evidence is reused, changed readings are re-fetched
                  </p>
                </div>
                <button
                  type="button"
                  className="btn-pill-ghost ml-auto shrink-0"
                  onClick={() => socket.send({ type: "plan.resume", data: { plan_id: plan.plan_id } })}
                >
                  Resume
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
