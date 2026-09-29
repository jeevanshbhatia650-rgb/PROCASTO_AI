import { useStore } from "../../lib/store";
import type { Clause } from "../../types/generated";

const INTENT_LABEL: Record<Clause["intent"], string> = {
  status: "status",
  error_lookup: "error lookup",
  energy: "energy use",
  action: "device action",
  resume: "go back",
  cancel: "cancel",
};

/** F6: the clauses pulled out of the sentence so far. Solid = stable (seen twice), dashed = still forming. */
export function TranscriptPanel() {
  const transcript = useStore((s) => s.transcript);
  const plan = useStore((s) => s.plan);
  const devices = useStore((s) => s.devices);
  const clauses = transcript?.clauses ?? [];
  const name = (id: string | null) => (id ? devices[id]?.info.display_name : undefined);

  return (
    <section className="card p-5" aria-label="What it understood">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="t-caption-strong">What it understood</h3>
        {plan && <span className="t-fine tabular text-ink-48">plan {plan.plan_id} · revision {plan.revision}</span>}
      </div>
      <p className="t-fine mt-0.5 text-ink-48">A clause becomes stable once it survives two partial transcripts in a row.</p>
      <div className="mt-3 flex min-h-8 flex-wrap gap-2">
        {transcript?.is_correction && (
          <span className="rounded-full bg-primary/10 px-3 py-1 t-fine font-semibold text-primary">Correction</span>
        )}
        {clauses.length === 0 && <span className="t-caption text-ink-48">Nothing yet. Start a sentence.</span>}
        {clauses.map((clause) => (
          <span
            key={clause.clause_id}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 t-fine transition-colors duration-150 ${
              clause.stable ? "bg-ink text-white" : "border border-dashed border-ink/30 text-ink-80"
            }`}
          >
            {name(clause.device_id) ?? "which device?"} · {INTENT_LABEL[clause.intent]}
            {clause.error_code ? ` ${clause.error_code}` : ""}
            <span className={clause.stable ? "text-ok-dark" : "text-ink-48"}>{clause.stable ? "stable" : "forming"}</span>
          </span>
        ))}
      </div>
    </section>
  );
}
