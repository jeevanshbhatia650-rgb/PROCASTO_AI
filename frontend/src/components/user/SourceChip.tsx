import type { Source } from "../../types/generated";
import { timeAgo } from "../../lib/format";
import { BookIcon, ChatIcon } from "../icons";

const RECENT_MS = 20_000;

/**
 * F13: where a card's facts came from, and how fresh they are. A live reading stays "watching" after it's
 * fetched: any material change to the device invalidates it and re-fetches it on its own (F14).
 */
export function SourceChip({ source, now }: { source: Source; now: number }) {
  const base = "inline-flex items-center gap-1.5 rounded-full bg-parchment px-2.5 py-1 t-fine text-ink-80";
  if (source.kind === "live_state") {
    const age = source.observed_at ? now - Date.parse(source.observed_at) : Number.POSITIVE_INFINITY;
    const label = age < RECENT_MS ? timeAgo(source.observed_at, now) : "watching";
    return (
      <span
        className={base}
        title={`Live device state, read ${timeAgo(source.observed_at, now)}. Any real change to the device re-fetches it automatically.`}
      >
        <span className="h-1.5 w-1.5 rounded-full bg-ok" />
        Live · {label}
      </span>
    );
  }
  const Icon = source.kind === "manual" ? BookIcon : ChatIcon;
  return (
    <span className={base} title={source.kind === "manual" ? "Retrieved from the device manual" : "From this conversation"}>
      <Icon size={13} />
      {source.label}
    </span>
  );
}
