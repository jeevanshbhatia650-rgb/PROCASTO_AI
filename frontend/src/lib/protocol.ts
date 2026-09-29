import type {
  AnswerCard,
  Clause,
  DeviceSnapshot,
  Metrics,
  ParkedPlan,
  QueryPlan,
  RetrievalTask,
  Span,
  TimelineEvent,
} from "../types/generated";

export type Hello = {
  session_id: string;
  provider: "simulator" | "smartthings";
  llm: string;
  dense_model: string | null;
  smartthings_connected: boolean;
};

export type ClausesUpdate = {
  utterance_id: string;
  text: string;
  final: boolean;
  clauses: Clause[];
  spans: Span[];
  is_correction: boolean;
  mentions: string[]; // devices named after a correction marker ("wait, I meant the dryer")
};

export type SpeechSay = { text: string; card_id: string; priority: "normal" | "update" };
export type DemoStep = { index?: number; total?: number; text?: string; done?: boolean };
type Empty = Record<string, never>;

export type ServerMessage =
  | { type: "hello"; data: Hello }
  | { type: "devices.snapshot"; data: DeviceSnapshot[] }
  | { type: "device.update"; data: DeviceSnapshot }
  | { type: "clauses.update"; data: ClausesUpdate }
  | { type: "plan.update"; data: QueryPlan | null }
  | { type: "parked.update"; data: ParkedPlan[] }
  | { type: "task.update"; data: RetrievalTask }
  | { type: "card.upsert"; data: AnswerCard }
  | { type: "card.remove"; data: { card_id: string } }
  | { type: "speech.say"; data: SpeechSay }
  | { type: "speech.stop"; data: Empty }
  | { type: "timeline.event"; data: TimelineEvent }
  | { type: "metrics.update"; data: Metrics }
  | { type: "demo.step"; data: DemoStep }
  | { type: "ui.hood"; data: { open: boolean } }
  | { type: "session.reset"; data: Empty }
  | { type: "error"; data: { message: string } };

export type ClientMessage =
  | { type: "transcript.partial" | "transcript.final"; data: { text: string; seq: number } }
  | { type: "speech.barge_in" | "speech.done"; data: Empty }
  | { type: "action.confirm"; data: { card_id: string; confirmed: boolean } }
  | { type: "plan.resume"; data: { plan_id: string } }
  | { type: "replay.start"; data: { script_id: string } };
