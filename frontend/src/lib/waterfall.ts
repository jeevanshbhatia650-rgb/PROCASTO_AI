import type { RetrievalTask, TaskStatus, TimelineEvent } from "../types/generated";

export type Utterance = { id: string; text: string; start: number; end: number | null };
type Word = { text: string; t: number };
type Bar = { id: string; label: string; start: number; end: number; status: TaskStatus };
export type Marker = { t: number; label: string; tone: "bad" | "info" | "park" };
export type Waterfall = {
  start: number;
  end: number;
  words: Word[];
  clauses: Marker[];
  bars: Bar[];
  events: Marker[];
  spokeEnd: number | null;
  leadMs: number | null;
};

const PAD_BEFORE_MS = 200;
const PAD_AFTER_MS = 350;
const MIN_SPAN_MS = 1600;
const SOURCE_LABEL: Record<string, string> = { live_state: "live", manual: "manual", session: "session" };

type Names = Record<string, string>;
const detail = (e: TimelineEvent) => e.detail as Record<string, unknown>;

/** Utterances in the order they were spoken, from transcript events. */
export function utterances(timeline: TimelineEvent[]): Utterance[] {
  const byId = new Map<string, Utterance>();
  for (const e of timeline) {
    if (e.kind !== "transcript") continue;
    const d = detail(e);
    const id = String(d.utterance_id);
    const current = byId.get(id) ?? { id, text: "", start: e.t_ms, end: null };
    byId.set(id, { ...current, text: String(d.text), end: d.final ? e.t_ms : current.end });
  }
  return [...byId.values()];
}

function words(timeline: TimelineEvent[], utteranceId: string): Word[] {
  const out: Word[] = [];
  for (const e of timeline) {
    const d = detail(e);
    if (e.kind !== "transcript" || d.utterance_id !== utteranceId) continue;
    const parts = String(d.text).split(/\s+/).filter(Boolean);
    for (let i = out.length; i < parts.length; i++) out.push({ text: parts[i] ?? "", t: e.t_ms });
  }
  return out;
}

function marker(e: TimelineEvent, names: Names): Marker | null {
  const d = detail(e);
  const name = names[String(d.device_id)] ?? "";
  switch (e.kind) {
    case "clause": {
      const what = d.error_code ? String(d.error_code) : String(d.intent).replace("_", " ");
      return { t: e.t_ms, label: `${name.toLowerCase()} · ${what}${d.origin === "auto" ? " (auto)" : ""}`, tone: d.origin === "auto" ? "bad" : "info" };
    }
    case "device_event":
      if (d.attribute !== "state") return null;
      return { t: e.t_ms, label: `${name} → ${String(d.new).toLowerCase()}`, tone: d.new === "ERROR" ? "bad" : "info" };
    case "interrupt":
      return { t: e.t_ms, label: "you cut in", tone: "info" };
    case "park":
      return { t: e.t_ms, label: "parked", tone: "park" };
    case "resume":
      return d.missed ? null : { t: e.t_ms, label: "resumed", tone: "park" };
    default:
      return null;
  }
}

/** Everything that happened around one utterance, on one time axis (session milliseconds). */
export function buildWaterfall(
  timeline: TimelineEvent[],
  tasks: Record<string, RetrievalTask>,
  utterance: Utterance,
  next: Utterance | undefined,
  nowMs: number,
  names: Names,
): Waterfall {
  const hardStop = next ? next.start - 1 : Number.POSITIVE_INFINITY;
  const inRange = (t: number) => t >= utterance.start - PAD_BEFORE_MS && t <= hardStop;
  const bars: Bar[] = Object.values(tasks)
    .filter((task) => task.started_ms != null && inRange(task.started_ms))
    .map((task) => ({
      id: task.task_id,
      label: `${task.task_id} ${SOURCE_LABEL[task.kind] ?? task.kind} · ${(names[task.device_id ?? ""] ?? "").toLowerCase()}`,
      start: task.started_ms ?? 0,
      end: task.finished_ms ?? Math.min(nowMs, hardStop),
      status: task.status,
    }))
    .sort((a, b) => a.start - b.start || a.id.localeCompare(b.id, undefined, { numeric: true }));
  const scoped = timeline.filter((e) => inRange(e.t_ms));
  const toMarkers = (list: TimelineEvent[]) =>
    list.map((e) => marker(e, names)).filter((m): m is Marker => m !== null);
  const clauses = toMarkers(scoped.filter((e) => e.kind === "clause"));
  const events = toMarkers(scoped.filter((e) => e.kind !== "clause"));
  const spokeEnd = utterance.end;
  const early = bars.filter((b) => spokeEnd !== null && b.start <= spokeEnd).map((b) => b.start);
  const leadMs = spokeEnd !== null && early.length ? spokeEnd - Math.min(...early) : null;
  const marks = [...clauses, ...events].map((m) => m.t);
  const latest = Math.max(spokeEnd ?? Math.min(nowMs, hardStop), ...bars.map((b) => b.end), ...marks);
  const start = utterance.start - PAD_BEFORE_MS;
  const end = Math.min(Math.max(latest + PAD_AFTER_MS, start + MIN_SPAN_MS), hardStop + PAD_AFTER_MS);
  return { start, end, words: words(timeline, utterance.id), clauses, bars, events, spokeEnd, leadMs };
}
