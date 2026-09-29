import { AnimatePresence, motion } from "motion/react";
import { formatSeconds } from "../../lib/format";
import { useStore } from "../../lib/store";
import type { RetrievalTask, TaskStatus } from "../../types/generated";

const MAX_ROWS = 7;
const KIND: Record<RetrievalTask["kind"], string> = { live_state: "Live state", manual: "Manual", session: "Session" };
const STATUS: Record<TaskStatus, { dot: string; text: string; label: string }> = {
  pending: { dot: "bg-off", text: "text-ink-48", label: "queued" },
  running: { dot: "bg-run", text: "text-run-text", label: "fetching" },
  done: { dot: "bg-ok", text: "text-ok-text", label: "done" },
  cancelled: { dot: "bg-off", text: "text-ink-48", label: "cancelled" },
  parked: { dot: "bg-primary", text: "text-primary", label: "parked" },
  stale: { dot: "bg-bad", text: "text-bad-text", label: "stale" },
};
const EASE_OUT = [0.23, 1, 0.32, 1] as const;

function detail(task: RetrievalTask): string {
  if (task.note) return task.note;
  if (task.kind === "manual") return `“${task.query}”`;
  return task.kind === "session" ? "recent turns" : "current reading";
}

/** F7 + F8: every retrieval the plan started, and what happened to it. */
export function TaskList() {
  const tasks = useStore((s) => s.tasks);
  const devices = useStore((s) => s.devices);
  const rows = Object.values(tasks)
    .sort((a, b) => Number(b.task_id.slice(1)) - Number(a.task_id.slice(1)))
    .slice(0, MAX_ROWS);

  return (
    <section className="card p-5" aria-label="What it's fetching">
      <h3 className="t-caption-strong">What it’s fetching</h3>
      <p className="t-fine mt-0.5 text-ink-48">Retrievals run in parallel. Corrections cancel or park only what they affect.</p>
      {rows.length === 0 && <p className="t-caption mt-3 text-ink-48">No retrievals yet.</p>}
      <ul className="mt-3 divide-y divide-divider">
        <AnimatePresence initial={false}>
          {rows.map((task) => {
            const s = STATUS[task.status];
            const done = task.status === "done" && task.started_ms != null && task.finished_ms != null;
            const struck = task.status === "cancelled" || task.status === "stale";
            return (
              <motion.li
                key={task.task_id}
                layout="position"
                initial={{ opacity: 0, transform: "translateY(-4px)" }}
                animate={{ opacity: 1, transform: "translateY(0px)" }}
                exit={{ opacity: 0, transition: { duration: 0.12 } }}
                transition={{ duration: 0.16, ease: EASE_OUT, layout: { type: "spring", bounce: 0, duration: 0.25 } }}
                className="flex items-center gap-3 py-2"
              >
                <span className={`h-2 w-2 shrink-0 rounded-full transition-colors duration-150 ${s.dot}`} />
                <span className="t-mono w-8 shrink-0 text-ink-48">{task.task_id}</span>
                <span className={`min-w-0 flex-1 truncate t-caption ${struck ? "text-ink-48 line-through" : "text-ink"}`}>
                  {KIND[task.kind]} · {devices[task.device_id ?? ""]?.info.display_name.toLowerCase() ?? "?"}
                  <span className="text-ink-48"> · {detail(task)}</span>
                </span>
                <span className={`t-fine tabular shrink-0 ${s.text}`}>
                  {done ? formatSeconds((task.finished_ms ?? 0) - (task.started_ms ?? 0)) : s.label}
                </span>
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ul>
    </section>
  );
}
