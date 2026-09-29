import type { TimelineEvent } from "../types/generated";
import { formatPower } from "./format";

export type FeedLine = { key: string; t: number; text: string; tone: "bad" | "warn" | "info" | "park" | "ok" };

type Names = Record<string, string>;

function deviceLine(d: Record<string, unknown>, name: string): Omit<FeedLine, "key" | "t"> | null {
  const { attribute, old, new: value } = d as { attribute: string; old: unknown; new: unknown };
  switch (attribute) {
    case "state":
      return { text: `${name}: ${String(old ?? "?").toLowerCase()} → ${String(value).toLowerCase()}`, tone: value === "ERROR" ? "bad" : "info" };
    case "error_code":
      return value ? { text: `${name} reported error ${String(value)}`, tone: "bad" } : { text: `${name} cleared its error`, tone: "ok" };
    case "remaining_min":
      return { text: `${name}: ${String(value)} min left`, tone: "info" };
    case "power_w":
      return { text: `${name} power ${formatPower(old as number)} → ${formatPower(value as number)}`, tone: "warn" };
    case "target_temp_c":
      return { text: `${name} target ${String(old)} → ${String(value)} °C`, tone: "info" };
    case "temp_c":
      return { text: `${name} now ${String(value)} °C`, tone: "info" };
    default:
      return null;
  }
}

/** Plain-English lines for the "What changed" feed. Returns null for events the feed doesn't show. */
export function describe(event: TimelineEvent, names: Names): FeedLine | null {
  const d = event.detail as Record<string, unknown>;
  const name = names[String(d.device_id)] ?? "Device";
  const line = (text: string, tone: FeedLine["tone"]): FeedLine => ({ key: `${event.t_ms}-${event.kind}-${text}`, t: event.t_ms, text, tone });
  const list = (value: unknown) => (Array.isArray(value) ? value.join(", ") : "");
  switch (event.kind) {
    case "device_event": {
      const described = deviceLine(d, name);
      return described ? line(described.text, described.tone) : null;
    }
    case "invalidate":
      return line(`${name} changed: ${list(d.stale)} stale, fetching ${list(d.replaced_by)}`, "warn");
    case "stale_drop":
      return line(`Dropped late result ${String(d.task_id)} (plan moved on)`, "warn");
    case "interrupt":
      return line(`You cut in. Voice stopped${d.llm_cancelled ? ", phrasing cancelled" : ""}`, "info");
    case "park":
      return line(`Parked “${String(d.label)}”`, "park");
    case "resume":
      return d.missed
        ? line(`Nothing parked for ${name}`, "info")
        : line(`Resumed: ${(d.reused as unknown[]).length} reused · ${(d.refetched as unknown[]).length} refetched`, "park");
    case "clause":
      return d.origin === "auto" ? line(`Auto-added: look up ${String(d.error_code)} for the ${name.toLowerCase()}`, "bad") : null;
    case "command":
      return line(d.ok ? `Sent ${String(d.command).replaceAll("_", " ")} to the ${name}` : `The ${name} rejected ${String(d.command)}`, d.ok ? "ok" : "bad");
    default:
      return null;
  }
}
