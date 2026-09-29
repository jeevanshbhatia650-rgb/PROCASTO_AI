import { AnimatePresence, motion } from "motion/react";
import type { ReactNode } from "react";

interface SplitPaneProps {
  hoodOpen: boolean;
  left: ReactNode;
  right: ReactNode;
}

const EASE_OUT = [0.23, 1, 0.32, 1] as const;

/**
 * The user view keeps its reading width; the engine column opens beside it. The grid track itself transitions
 * (a rare, deliberate layout change, like an accordion) and the engine content slides in from the side it lives on.
 */
export function SplitPane({ hoodOpen, left, right }: SplitPaneProps) {
  return (
    <div className={`split ${hoodOpen ? "split-open" : ""}`}>
      <div className="min-w-0">
        <div className="mx-auto w-full max-w-[920px]">{left}</div>
      </div>
      <div className="min-w-0" aria-hidden={!hoodOpen} inert={!hoodOpen}>
        <AnimatePresence initial={false}>
          {hoodOpen && (
            <motion.div
              key="hood"
              initial={{ opacity: 0, transform: "translateX(16px)" }}
              animate={{ opacity: 1, transform: "translateX(0px)" }}
              exit={{ opacity: 0, transform: "translateX(16px)", transition: { duration: 0.16, ease: EASE_OUT } }}
              transition={{ duration: 0.26, ease: EASE_OUT, delay: 0.06 }}
            >
              {right}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
