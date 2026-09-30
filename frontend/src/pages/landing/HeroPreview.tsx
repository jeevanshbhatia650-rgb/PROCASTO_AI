import { BookOpenCheck, Radio, WashingMachine } from "lucide-react";
import { Ring } from "../../components/glass/Ring";

/** A still of the product answering one question, so a first-time visitor sees what it does before reading. */
export function HeroPreview() {
  return (
    <div className="glass-panel relative mx-auto w-full max-w-[1040px] rounded-xl p-3 sm:p-5" aria-label="Example answer">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-1 pb-3 sm:pb-4">
        <p className="order-first w-full rounded-full bg-white/70 px-3 py-1.5 text-center t-caption text-ink-80 sm:order-none sm:ml-auto sm:w-auto">
          “Why did my washer stop?”
        </p>
        <p className="flex items-center gap-2 t-fine text-ink-48 sm:order-first">
          <span className="h-2.5 w-2.5 rounded-full bg-ok" aria-hidden="true" /> Live · Laundry room
        </p>
      </div>
      <div className="grid gap-3 sm:gap-4 md:grid-cols-[0.9fr_1.6fr_0.9fr]">
        <article className="tile-dark p-5">
          <div className="flex items-center gap-2 t-fine text-white/60">
            <WashingMachine size={16} aria-hidden="true" />
            <span>Washer</span>
            <span className="ml-auto">WW90T</span>
          </div>
          <p className="t-display mt-6">Stopped</p>
          <p className="mt-2 flex items-center gap-2 t-caption text-bad-dark">
            <span className="h-1.5 w-1.5 rounded-full bg-bad-dark" aria-hidden="true" />
            Error E3 · 0 W
          </p>
          <div className="mt-6 h-1 rounded-full bg-white/10">
            <div className="h-full w-[62%] rounded-full bg-bad-dark/80" />
          </div>
        </article>

        <article className="card p-5 sm:p-6">
          <p className="t-eyebrow text-bad-text">Problem</p>
          <h3 className="t-tagline mt-2">E3 · Water not draining</h3>
          <p className="t-caption mt-2 text-ink-80">
            The pump can't empty the drum, so the cycle stopped with water inside. Clean the drain filter behind the
            small flap at the bottom left, then run Rinse + Spin.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-ok/12 px-3 py-1 t-fine text-ok-text">
              <Radio size={13} aria-hidden="true" /> Live · just now
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-chip px-3 py-1 t-fine text-ink-80">
              <BookOpenCheck size={13} aria-hidden="true" /> WW90T sample manual §E3 p.41
            </span>
          </div>
        </article>

        <article className="card flex flex-col items-center justify-center p-5 text-center">
          <Ring value={0.78} label="Head start">
            <p className="t-section tabular">2.4 s</p>
          </Ring>
          <p className="t-caption-strong mt-3">Head start</p>
          <p className="t-fine mt-1 text-ink-48">The lookup began this long before the question ended.</p>
        </article>
      </div>
    </div>
  );
}
