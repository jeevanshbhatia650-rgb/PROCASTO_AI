import { create } from "zustand";
import type {
  AnswerCard,
  DeviceSnapshot,
  Metrics,
  ParkedPlan,
  QueryPlan,
  RetrievalTask,
  TimelineEvent,
} from "../types/generated";
import type { AgentRun, AgentsStats, ClausesUpdate, DemoStep, Hello, ServerMessage, SpeechSay } from "./protocol";

type Turn = { id: string; text: string };
type Connection = "connecting" | "open" | "closed";

export type Data = {
  connection: Connection;
  hello: Hello | null;
  devices: Record<string, DeviceSnapshot>;
  transcript: ClausesUpdate | null;
  turns: Turn[];
  plan: QueryPlan | null;
  parked: ParkedPlan[];
  tasks: Record<string, RetrievalTask>;
  cards: Record<string, AnswerCard>;
  timeline: TimelineEvent[];
  metrics: Metrics;
  speech: (SpeechSay & { id: number }) | null;
  stopSpeech: number;
  demo: DemoStep | null;
  hoodOpen: boolean;
  voiceOn: boolean;
  toast: { id: number; message: string } | null;
  clockOffset: number; // Date.now() minus the server's session clock, to place "now" on the timeline
  power: number[]; // whole-home watts, one sample every POWER_SAMPLE_MS, oldest first
  agentRun: AgentRun | null; // the latest diagnose-and-act run
  agentBusy: string | null; // the device a run is working on, until its report arrives
  agentsStats: AgentsStats | null;
};

const MAX_TIMELINE = 500;
export const POWER_SAMPLE_MS = 3000;
export const MAX_POWER_SAMPLES = 40;
const EMPTY_POWER: number[] = [];
const MAX_TASKS = 60;
const EMPTY_METRICS: Metrics = {
  lead_time_ms: null,
  best_lead_time_ms: null,
  first_card_ms: null,
  tasks_reused: 0,
  tasks_refetched: 0,
};

export const initialData: Data = {
  connection: "connecting",
  hello: null,
  devices: {},
  transcript: null,
  turns: [],
  plan: null,
  parked: [],
  tasks: {},
  cards: {},
  timeline: [],
  metrics: EMPTY_METRICS,
  speech: null,
  stopSpeech: 0,
  demo: null,
  hoodOpen: false,
  voiceOn: true,
  toast: null,
  clockOffset: 0,
  power: EMPTY_POWER,
  agentRun: null,
  agentBusy: null,
  agentsStats: null,
};

const SESSION_RESET = {
  transcript: null, turns: [], plan: null, parked: [], tasks: {}, cards: {}, timeline: [],
  metrics: EMPTY_METRICS, speech: null, demo: null, power: EMPTY_POWER, agentRun: null, agentBusy: null,
} satisfies Partial<Data>;

let counter = 0;
const nextId = () => ++counter;

function withTask(tasks: Record<string, RetrievalTask>, task: RetrievalTask): Record<string, RetrievalTask> {
  const next = { ...tasks, [task.task_id]: task };
  const ids = Object.keys(next);
  if (ids.length <= MAX_TASKS) return next;
  const byAge = ids.sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)));
  for (const id of byAge.slice(0, ids.length - MAX_TASKS)) delete next[id];
  return next;
}

export function totalPower(devices: Record<string, DeviceSnapshot>): number {
  return Object.values(devices).reduce((sum, d) => sum + (Number(d.attributes.power_w) || 0), 0);
}

/** Sampled on a clock, not on updates: a quiet home still draws a line, and every step is the same length of time. */
export function withPowerSample(power: number[], devices: Record<string, DeviceSnapshot>): number[] {
  return [...power.slice(-(MAX_POWER_SAMPLES - 1)), totalPower(devices)];
}

function without<T>(record: Record<string, T>, key: string): Record<string, T> {
  const next = { ...record };
  delete next[key];
  return next;
}

/** Pure: server message in, state changes out. */
export function reduce(state: Data, msg: ServerMessage, receivedAt = Date.now()): Partial<Data> {
  switch (msg.type) {
    case "hello": // a new server session: nothing from the previous one still applies
      return { ...SESSION_RESET, devices: {}, stopSpeech: state.stopSpeech + 1, hello: msg.data };
    case "devices.snapshot":
      return { devices: Object.fromEntries(msg.data.map((d) => [d.info.device_id, d])) };
    case "device.update":
      return { devices: { ...state.devices, [msg.data.info.device_id]: msg.data } };
    case "clauses.update": {
      const turns = msg.data.final ? [...state.turns.slice(-3), { id: msg.data.utterance_id, text: msg.data.text }] : state.turns;
      return { transcript: msg.data, turns };
    }
    case "plan.update":
      return { plan: msg.data };
    case "parked.update":
      return { parked: msg.data };
    case "task.update":
      return { tasks: withTask(state.tasks, msg.data) };
    case "card.upsert":
      return { cards: { ...state.cards, [msg.data.card_id]: msg.data } };
    case "card.remove":
      return { cards: without(state.cards, msg.data.card_id) };
    case "speech.say":
      return { speech: { ...msg.data, id: nextId() } };
    case "speech.stop":
      return { speech: null, stopSpeech: state.stopSpeech + 1 };
    case "timeline.event":
      return { timeline: [...state.timeline.slice(-(MAX_TIMELINE - 1)), msg.data], clockOffset: receivedAt - msg.data.t_ms };
    case "metrics.update":
      return { metrics: msg.data };
    case "demo.step":
      return { demo: msg.data.done ? null : msg.data };
    case "ui.hood":
      return { hoodOpen: msg.data.open };
    case "session.reset":
      return { ...SESSION_RESET, stopSpeech: state.stopSpeech + 1 };
    case "agent.update":
      return { agentRun: msg.data, agentBusy: null };
    case "agents.stats":
      return { agentsStats: msg.data };
    case "error":
      return { toast: { id: nextId(), message: msg.data.message }, agentBusy: null };
  }
}

type Actions = {
  apply: (msg: ServerMessage) => void;
  setConnection: (connection: Connection) => void;
  setHood: (open: boolean) => void;
  toggleVoice: () => void;
  showToast: (message: string) => void;
  samplePower: () => void;
  startAgent: (deviceId: string) => void;
  clearPrivate: () => void;
};

export const useStore = create<Data & Actions>()((set) => ({
  ...initialData,
  apply: (msg) => set((state) => reduce(state, msg)),
  setConnection: (connection) => set({ connection }),
  setHood: (hoodOpen) => set({ hoodOpen }),
  toggleVoice: () => set((state) => ({ voiceOn: !state.voiceOn })),
  showToast: (message) => set({ toast: { id: nextId(), message } }),
  samplePower: () =>
    set((state) => (Object.keys(state.devices).length ? { power: withPowerSample(state.power, state.devices) } : state)),
  startAgent: (deviceId) => set({ agentBusy: deviceId, agentRun: null }),
  clearPrivate: () => set((state) => ({ ...initialData, connection: "closed", stopSpeech: state.stopSpeech + 1 })),
}));
