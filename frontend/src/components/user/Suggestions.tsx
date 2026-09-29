import { useMemo } from "react";
import { useStore } from "../../lib/store";
import { suggestions } from "../../lib/suggestions";

interface SuggestionsProps {
  onAsk: (question: string) => void;
}

/** Smart options: questions worth asking right now, read from the live home. */
export function Suggestions({ onAsk }: SuggestionsProps) {
  const devices = useStore((s) => s.devices);
  const parked = useStore((s) => s.parked);
  const items = useMemo(() => suggestions(Object.values(devices), parked), [devices, parked]);
  return (
    <div className="mt-4 flex flex-wrap items-center gap-2">
      <span className="t-fine text-ink-48">Try</span>
      {items.map((question) => (
        <button
          key={question}
          type="button"
          onClick={() => onAsk(question)}
          className="pressable rounded-full border border-black/[0.08] bg-canvas px-4 py-2 t-caption text-ink-80 transition-[border-color,transform] duration-150 hover:border-primary/40"
        >
          {question}
        </button>
      ))}
    </div>
  );
}
