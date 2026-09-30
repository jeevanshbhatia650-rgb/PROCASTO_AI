import { BookOpenCheck, BookOpenText, Check, LoaderCircle, Radio, SlidersHorizontal, Workflow, X, type LucideIcon } from "lucide-react";
import type { AgentReport } from "../../lib/protocol";
import { useStore } from "../../lib/store";
import { socket } from "../../lib/ws";
import { DeviceIcon } from "../icons";

const AGENTS: { id: AgentReport["agent"]; name: string; what: string; Icon: LucideIcon }[] = [
  { id: "home_state", name: "Home State agent", what: "Reads the live snapshot, kept fresh by pushed device events.", Icon: Radio },
  { id: "manual", name: "Manual agent", what: "Hybrid keyword + meaning search over the manual, cached.", Icon: BookOpenText },
  { id: "preferences", name: "Preference agent", what: "Looks up how you usually run this device.", Icon: SlidersHorizontal },
];

function AgentTile({ agent, report, busy }: { agent: (typeof AGENTS)[number]; report?: AgentReport; busy: boolean }) {
  const { Icon } = agent;
  return (
    <li className="flex gap-3 rounded-lg border border-black/[0.06] bg-white/70 p-4">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-ink text-white">
        <Icon size={18} aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="t-caption-strong">{agent.name}</p>
        {busy ? (
          <p className="mt-0.5 inline-flex items-center gap-1.5 t-fine text-ink-48">
            <LoaderCircle size={13} className="animate-spin" aria-hidden="true" /> Working…
          </p>
        ) : report ? (
          <>
            <p className="mt-0.5 t-fine tabular text-ok-text">{report.ms < 1 ? "< 1" : report.ms.toFixed(0)} ms</p>
            <p className="mt-1 t-fine text-ink-80">{report.detail}</p>
          </>
        ) : (
          <p className="mt-0.5 t-fine text-ink-48">{agent.what}</p>
        )}
      </div>
    </li>
  );
}

/** The LangGraph agent: three agents look at one device side by side, propose a fix, and act only after a yes. */
export function AgentPanel() {
  const devices = Object.values(useStore((s) => s.devices));
  const busy = useStore((s) => s.agentBusy);
  const run = useStore((s) => s.agentRun);
  const startAgent = useStore((s) => s.startAgent);
  const showToast = useStore((s) => s.showToast);
  const selected = busy ?? run?.device_id ?? null;
  const name = (id: string) => devices.find((d) => d.info.device_id === id)?.info.display_name ?? "device";

  const start = (deviceId: string) => {
    if (socket.send({ type: "agent.start", data: { device_id: deviceId } })) startAgent(deviceId);
    else showToast("Not connected yet. Try again in a second.");
  };
  const decide = (approve: boolean) => {
    if (run) socket.send({ type: "agent.decide", data: { thread_id: run.thread_id, approve } });
  };

  return (
    <section aria-labelledby="agents-title" className="mt-10">
      <div className="mb-1 flex flex-wrap items-baseline gap-3">
        <h2 id="agents-title" className="t-section">
          Diagnose &amp; fix
        </h2>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-ink/[0.06] px-2.5 py-1 t-fine text-ink-80">
          <Workflow size={13} aria-hidden="true" /> 3 agents · LangGraph
        </span>
      </div>
      <p className="t-caption text-ink-48">
        Pick a device. Three agents look at it at the same time, then one fix is proposed. Nothing changes until you say yes.
      </p>

      <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Device to diagnose">
        {devices.slice(0, 8).map((d) => (
          <button
            key={d.info.device_id}
            type="button"
            onClick={() => start(d.info.device_id)}
            disabled={busy !== null}
            aria-pressed={selected === d.info.device_id}
            className={`pressable inline-flex items-center gap-2 rounded-full px-4 py-2 t-caption ${
              selected === d.info.device_id ? "bg-ink text-white" : "bg-white/70 text-ink-80 hover:bg-white"
            }`}
          >
            <DeviceIcon kind={d.info.kind} size={16} /> {d.info.display_name}
          </button>
        ))}
      </div>

      <ul className="mt-4 grid gap-3 md:grid-cols-3" aria-label="The three agents">
        {AGENTS.map((agent) => (
          <AgentTile key={agent.id} agent={agent} busy={busy !== null} report={run?.agents.find((a) => a.agent === agent.id)} />
        ))}
      </ul>

      {run && !busy && (
        <div className="mt-3 rounded-lg border border-black/[0.06] bg-white p-5" aria-live="polite">
          <p className="t-fine text-ink-48">
            {name(run.device_id)} · the three agents answered in {Math.max(1, ...run.agents.map((a) => a.ms)).toFixed(0)} ms, side
            by side (the slowest, not the sum) · with the proposal {run.total_ms.toFixed(0)} ms
          </p>
          <p className="mt-2 t-body">{run.explanation}</p>
          {run.steps.length > 0 && (
            <ol className="mt-3 space-y-1.5">
              {run.steps.map((step, i) => (
                <li key={i} className="flex gap-3 t-caption text-ink-80">
                  <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-ink/[0.06] t-fine">{i + 1}</span>
                  {step}
                </li>
              ))}
            </ol>
          )}
          {run.sources.length > 0 && (
            <p className="mt-3 flex flex-wrap gap-1.5">
              {run.sources.map((s) => (
                <span key={s} className="inline-flex items-center gap-1 rounded-full bg-ink/[0.05] px-2.5 py-1 t-fine text-ink-80">
                  <BookOpenCheck size={12} aria-hidden="true" /> {s}
                </span>
              ))}
            </p>
          )}
          {run.stage === "waiting" && run.action && (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <button type="button" className="btn-pill" onClick={() => decide(true)}>
                <Check size={16} aria-hidden="true" /> {run.action.label}
              </button>
              <button type="button" className="btn-pill-ghost" onClick={() => decide(false)}>
                <X size={16} aria-hidden="true" /> Not now
              </button>
            </div>
          )}
          {run.outcome && (
            <p
              className={`mt-4 inline-flex items-center gap-2 rounded-full px-3 py-1.5 t-caption ${
                run.acted ? "bg-ok/12 text-ok-text" : "bg-ink/[0.06] text-ink-80"
              }`}
              role="status"
            >
              {run.acted && <Check size={15} aria-hidden="true" />} {run.outcome}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
