import { AnimatePresence, motion } from "motion/react";
import { useStore } from "../../lib/store";

const EASE_OUT = [0.23, 1, 0.32, 1] as const;

/** Narrates the replay so anyone watching knows what they're seeing. */
export function DemoCaption() {
  const demo = useStore((s) => s.demo);
  return (
    <div className="pointer-events-none fixed inset-x-0 top-[108px] z-30 flex justify-center px-4">
      <AnimatePresence>
        {demo?.text && (
          <motion.div
            key="caption"
            initial={{ opacity: 0, transform: "translateY(-6px)" }}
            animate={{ opacity: 1, transform: "translateY(0px)" }}
            exit={{ opacity: 0, transform: "translateY(-6px)", transition: { duration: 0.16 } }}
            transition={{ duration: 0.24, ease: EASE_OUT }}
            className="flex max-w-2xl items-center gap-3 rounded-full bg-ink/90 px-5 py-2.5 text-white backdrop-blur-md"
            role="status"
          >
            <span className="t-caption-strong tabular shrink-0 text-primary-on-dark">
              {demo.index}/{demo.total}
            </span>
            <motion.span
              key={demo.text}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
              className="t-caption"
            >
              {demo.text}
            </motion.span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
