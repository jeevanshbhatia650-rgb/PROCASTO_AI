import { LiveTranscript } from "../user/LiveTranscript";
import { AgentsStats } from "./AgentsStats";
import { EventFeed } from "./EventFeed";
import { LeadTimeBadge } from "./LeadTimeBadge";
import { TaskList } from "./TaskList";
import { Timeline } from "./Timeline";
import { TranscriptPanel } from "./TranscriptPanel";

/** The engine, shown so a judge can see it working: proof first, then the moving parts. */
export function HoodView() {
  return (
    <aside aria-label="Under the hood" className="flex flex-col gap-3 pb-6 pt-10">
      <section className="tile-dark p-6">
        <LeadTimeBadge />
        <div className="mt-6 border-t border-white/10 pt-5">
          <h3 className="t-caption-strong text-white">What happened, in time</h3>
          <p className="t-fine mt-0.5 text-white/50">Your words, the clauses heard, each retrieval, and changes in the home.</p>
          <div className="mt-3">
            <Timeline />
          </div>
        </div>
      </section>
      <section className="card p-5" aria-label="What it heard">
        <h3 className="t-caption-strong">What it heard</h3>
        <p className="t-fine mt-0.5 text-ink-48">Your words as they arrive. Coloured words are the ones it understood.</p>
        <div className="mt-3">
          <LiveTranscript />
        </div>
      </section>
      <TranscriptPanel />
      <AgentsStats />
      <TaskList />
      <EventFeed />
    </aside>
  );
}
