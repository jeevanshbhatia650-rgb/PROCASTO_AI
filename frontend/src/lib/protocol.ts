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
  home: "demo" | "smartthings";
  signed_in: boolean;
  notice: string; // why real devices aren't live right now, if they aren't
  llm: string;
  dense_model: string | null;
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

/** One of the three retrieval agents, as it reported on a diagnose run. */
export type AgentReport = { agent: "home_state" | "manual" | "preferences"; ms: number; detail: string; cache?: string };

/** A diagnose-and-act run of the LangGraph agent. `waiting` means it needs a yes or no before acting. */
export type AgentRun = {
  thread_id: string;
  device_id: string;
  stage: "waiting" | "done";
  agents: AgentReport[];
  total_ms: number;
  explanation: string;
  steps: string[];
  action: { device_id: string; command: string; args: Record<string, unknown>; label: string } | null;
  sources: string[];
  preferences: Record<string, unknown>;
  outcome: string | null;
  acted: boolean; // true only when a device really changed
};

export type AgentsStats = {
  cache: { hits: number; misses: number; hit_rate: number | null; prefetched: number; prefetch_hits: number } | null;
  preferences: Record<string, Record<string, unknown>>;
  domains: string[];
  push: boolean;
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
  | { type: "agent.update"; data: AgentRun }
  | { type: "agents.stats"; data: AgentsStats }
  | { type: "error"; data: { message: string } };

export type ScenarioId = "washer_e3" | "washer_done" | "ac_spike" | "dryer_done" | "reset";

export type ClientMessage =
  | { type: "auth"; data: { token: string | null } }
  | { type: "sim.trigger"; data: { scenario: ScenarioId } }
  | { type: "transcript.partial" | "transcript.final"; data: { text: string; seq: number } }
  | { type: "speech.barge_in" | "speech.done"; data: Empty }
  | { type: "action.confirm"; data: { card_id: string; confirmed: boolean } }
  | { type: "plan.resume"; data: { plan_id: string } }
  | { type: "replay.start"; data: { script_id: string } }
  | { type: "agent.start"; data: { device_id: string; question?: string } }
  | { type: "agent.decide"; data: { thread_id: string; approve: boolean } };
