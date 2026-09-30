/* Generated from backend/app/core/models.py by make types. Do not edit. */

/**
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "CardType".
 */
export type CardType = "status" | "problem" | "action" | "info" | "confirm";
/**
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "Intent".
 */
export type Intent = "status" | "error_lookup" | "energy" | "action" | "resume" | "cancel";
/**
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "DeviceKind".
 */
export type DeviceKind = "washer" | "dryer" | "ac" | "other";
export type TaskStatus = "pending" | "running" | "done" | "cancelled" | "parked" | "stale";
/**
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "TaskStatus".
 */
export type TaskStatus1 = "pending" | "running" | "done" | "cancelled" | "parked" | "stale";

export interface ProcastoContracts {
  AnswerCard?: AnswerCard;
  CardCommand?: CardCommand;
  Clause?: Clause;
  DeviceEvent?: DeviceEvent;
  DeviceInfo?: DeviceInfo;
  DeviceSnapshot?: DeviceSnapshot;
  Evidence?: Evidence;
  Metrics?: Metrics;
  ParkedPlan?: ParkedPlan;
  QueryPlan?: QueryPlan;
  RetrievalTask?: RetrievalTask;
  Source?: Source;
  Span?: Span;
  TimelineEvent?: TimelineEvent;
}
/**
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "AnswerCard".
 */
export interface AnswerCard {
  body: string;
  card_id: string;
  command: CardCommand | null;
  device_id: string | null;
  evidence_ids: string[];
  plan_id: string;
  plan_revision: number;
  severity: "ok" | "info" | "warn" | "error";
  sources: Source[];
  speakable: string;
  steps: string[];
  title: string;
  type: CardType;
}
/**
 * A device command the user can confirm from a card.
 *
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "CardCommand".
 */
export interface CardCommand {
  args: {
    [k: string]: unknown;
  };
  command: string;
  device_id: string;
  label: string;
}
/**
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "Source".
 */
export interface Source {
  kind: "live_state" | "manual" | "session";
  label: string;
  observed_at: string | null;
}
/**
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "Clause".
 */
export interface Clause {
  clause_id: string;
  device_id: string | null;
  error_code: string | null;
  first_seen_ms: number;
  intent: Intent;
  origin: "user" | "auto";
  params: {
    [k: string]: unknown;
  };
  stable: boolean;
}
/**
 * Normalized event. Simulator and SmartThings must both emit this.
 *
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "DeviceEvent".
 */
export interface DeviceEvent {
  attribute: "state" | "remaining_min" | "power_w" | "error_code" | "temp_c" | "target_temp_c";
  device_id: string;
  event_id: string;
  observed_at: string;
  source: "simulator" | "smartthings";
  value: unknown;
}
/**
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "DeviceInfo".
 */
export interface DeviceInfo {
  aliases: string[];
  device_id: string;
  display_name: string;
  family: string;
  kind: DeviceKind;
  model_id: string;
  room: string;
}
/**
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "DeviceSnapshot".
 */
export interface DeviceSnapshot {
  attributes: {
    [k: string]: unknown;
  };
  info: DeviceInfo;
  revision: number;
  updated_at: string;
}
/**
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "Evidence".
 */
export interface Evidence {
  authority: "simulator" | "smartthings" | "manual" | "session";
  citation: string;
  device_id: string | null;
  device_revision: number | null;
  evidence_id: string;
  model_id: string | null;
  observed_at: string;
  payload: {
    [k: string]: unknown;
  };
  plan_revision: number;
  source_type: "live_state" | "manual" | "session";
  task_id: string;
}
/**
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "Metrics".
 */
export interface Metrics {
  best_lead_time_ms: number | null;
  first_card_ms: number | null;
  lead_time_ms: number | null;
  tasks_refetched: number;
  tasks_reused: number;
}
/**
 * What the UI needs to show a parked plan and offer to resume it.
 *
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "ParkedPlan".
 */
export interface ParkedPlan {
  device_ids: string[];
  label: string;
  plan_id: string;
  task_count: number;
}
/**
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "QueryPlan".
 */
export interface QueryPlan {
  clauses: Clause[];
  created_at: string;
  label: string;
  plan_id: string;
  revision: number;
  tasks: RetrievalTask[];
}
/**
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "RetrievalTask".
 */
export interface RetrievalTask {
  clause_id: string;
  depends_on_device_rev: number | null;
  device_id: string | null;
  finished_ms: number | null;
  kind: "live_state" | "manual" | "session";
  note: string | null;
  plan_revision: number;
  query: string;
  started_ms: number | null;
  status: TaskStatus;
  task_id: string;
}
/**
 * A highlighted stretch of the transcript, for the live transcript view.
 *
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "Span".
 */
export interface Span {
  end: number;
  role: "device" | "intent" | "code" | "correction" | "pronoun";
  start: number;
}
/**
 * This interface was referenced by `ProcastoContracts`'s JSON-Schema
 * via the `definition` "TimelineEvent".
 */
export interface TimelineEvent {
  detail: {
    [k: string]: unknown;
  };
  kind:
    | "transcript"
    | "clause"
    | "task_start"
    | "task_done"
    | "task_cancel"
    | "task_park"
    | "park"
    | "stale_drop"
    | "device_event"
    | "invalidate"
    | "card"
    | "interrupt"
    | "resume"
    | "command";
  t_ms: number;
}
