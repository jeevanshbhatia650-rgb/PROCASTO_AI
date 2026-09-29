import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import type { AnswerCard } from "../../types/generated";
import { useStore } from "../../lib/store";
import { socket } from "../../lib/ws";

const EASE_OUT = [0.23, 1, 0.32, 1] as const;

/**
 * F24: nothing touches a device without an explicit yes. Spoken requests ("set the AC to 24") arrive as a
 * question card; suggestions on other cards ask for a second, explicit confirm before sending.
 */
export function ConfirmDialog({ card }: { card: AnswerCard }) {
  const [asking, setAsking] = useState(card.type === "confirm");
  const [sending, setSending] = useState(false);
  const devices = useStore((s) => s.devices);
  const command = card.command;
  if (!command) return null;
  const name = devices[command.device_id]?.info.display_name ?? "device";

  const answer = (confirmed: boolean) => {
    if (!socket.send({ type: "action.confirm", data: { card_id: card.card_id, confirmed } })) {
      useStore.getState().showToast("Not connected, so nothing was sent.");
      return;
    }
    setSending(confirmed);
    if (!confirmed && card.type !== "confirm") setAsking(false);
  };

  return (
    <div className="mt-4">
      <AnimatePresence initial={false} mode="wait">
        {asking ? (
          <motion.div
            key="ask"
            initial={{ opacity: 0, transform: "translateY(4px)" }}
            animate={{ opacity: 1, transform: "translateY(0px)" }}
            exit={{ opacity: 0, transition: { duration: 0.12 } }}
            transition={{ duration: 0.18, ease: EASE_OUT }}
            className="flex flex-wrap items-center gap-3"
          >
            {card.type !== "confirm" && (
              <span className="t-caption text-ink-80">
                Send “{command.label}” to the {name}?
              </span>
            )}
            <button type="button" className="btn-pill" disabled={sending} onClick={() => answer(true)}>
              {sending ? "Sending…" : card.type === "confirm" ? command.label : "Confirm"}
            </button>
            <button type="button" className="btn-utility" disabled={sending} onClick={() => answer(false)}>
              {card.type === "confirm" ? "Not now" : "Cancel"}
            </button>
          </motion.div>
        ) : (
          <motion.button
            key="offer"
            type="button"
            className="btn-pill-ghost"
            onClick={() => setAsking(true)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.12 } }}
          >
            {command.label}
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}
