import { ArrowRight, BookOpenCheck, CirclePlay, KeyRound, Lock, Mic, PlugZap, Radio, ShieldCheck, Trash } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { Logo } from "../../components/glass/Logo";
import { Reveal } from "../../components/glass/Reveal";

function SectionHead({ id, eyebrow, title, children }: { id: string; eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <Reveal className="mx-auto max-w-[720px] text-center">
      <p className="t-eyebrow text-ink-48">{eyebrow}</p>
      <h2 id={id} className="t-display mt-3">
        {title}
      </h2>
      {children && <p className="t-body mt-4 text-ink-80">{children}</p>}
    </Reveal>
  );
}

const STEPS = [
  {
    icon: PlugZap,
    title: "Connect SmartThings",
    body: "Sign in with your Samsung account. We read your washer, dryer and AC. Nothing is switched without your OK.",
  },
  {
    icon: Mic,
    title: "Ask like you'd ask a person",
    body: "Talk or type. Interrupt yourself, change your mind, come back to an earlier question: it keeps up.",
  },
  {
    icon: BookOpenCheck,
    title: "Get the answer and its source",
    body: "Live readings first, then your model's manual. Every fact is cited, and answers update when a device does.",
  },
];

export function HowItWorks() {
  return (
    <section id="how" className="scroll-mt-28 px-4 py-16 sm:px-8 sm:py-20" aria-labelledby="how-title">
      <SectionHead id="how-title" eyebrow="How it works" title="Three steps, then just ask." />
      <ol className="mx-auto mt-12 grid max-w-[1100px] gap-4 md:grid-cols-3">
        {STEPS.map(({ icon: Icon, title, body }, i) => (
          <Reveal key={title} delay={i * 70}>
            <li className="card h-full list-none p-6">
              <div className="flex items-center justify-between">
                <span className="grid h-11 w-11 place-items-center rounded-full bg-ink text-white">
                  <Icon size={20} aria-hidden="true" />
                </span>
                <span className="font-display text-[40px] font-light leading-none text-ink/15">0{i + 1}</span>
              </div>
              <h3 className="t-tagline mt-6">{title}</h3>
              <p className="t-caption mt-2 text-ink-80">{body}</p>
            </li>
          </Reveal>
        ))}
      </ol>
    </section>
  );
}

export function Different() {
  return (
    <section id="different" className="scroll-mt-28 px-4 py-16 sm:px-8 sm:py-20" aria-labelledby="different-title">
      <SectionHead id="different-title" eyebrow="What's different" title="Not another dashboard.">
        SmartThings already shows status. PROCASTO answers questions about it, from the right source, while you talk.
      </SectionHead>
      <div className="mx-auto mt-12 grid max-w-[1100px] gap-4 md:grid-cols-6">
        <Reveal className="md:col-span-4">
          <article className="tile-dark h-full p-7">
            <p className="t-eyebrow text-white/50">Starts before you finish</p>
            <h3 className="t-section mt-3">The lookup begins mid-sentence.</h3>
            <p className="t-caption mt-2 max-w-[460px] text-white/70">
              As soon as it's sure what you're asking about, it fetches the answer. You see exactly how early it started.
            </p>
            <div className="mt-8" aria-hidden="true">
              <div className="flex justify-between t-fine text-white/40">
                <span>“How long until the washer…</span>
                <span>…finishes?”</span>
              </div>
              <div className="relative mt-3 h-2 rounded-full bg-white/10">
                <div className="absolute inset-y-0 left-[38%] right-0 rounded-full bg-primary-on-dark/80" />
              </div>
              <div className="mt-2 flex justify-between t-fine">
                <span className="ml-[34%] text-primary-on-dark">lookup started</span>
                <span className="text-white/60">you finished · 2.4 s later</span>
              </div>
            </div>
          </article>
        </Reveal>
        <Reveal className="md:col-span-2" delay={70}>
          <article className="card h-full p-7">
            <p className="t-eyebrow text-ink-48">Two sources, one answer</p>
            <h3 className="t-tagline mt-3">Live state meets your manual.</h3>
            <div className="mt-6 space-y-2" aria-hidden="true">
              <p className="flex items-center gap-2 rounded-full bg-ok/12 px-3 py-1.5 t-fine text-ok-text">
                <Radio size={13} /> Washer stopped · E3
              </p>
              <p className="flex items-center gap-2 rounded-full bg-chip px-3 py-1.5 t-fine text-ink-80">
                <BookOpenCheck size={13} /> WW90T manual · p.41
              </p>
              <p className="rounded-lg bg-ink px-3 py-2 t-fine text-white">Clean the drain filter, then Rinse + Spin.</p>
            </div>
          </article>
        </Reveal>
        <Reveal className="md:col-span-3" delay={70}>
          <article className="card h-full p-7">
            <p className="t-eyebrow text-ink-48">Change your mind</p>
            <h3 className="t-tagline mt-3">“Wait, I meant the dryer.”</h3>
            <p className="t-caption mt-2 text-ink-80">
              The washer question is parked, not thrown away. Say “go back to the washer” and it returns, reusing what
              is still true and re-checking what changed.
            </p>
          </article>
        </Reveal>
        <Reveal className="md:col-span-3" delay={140}>
          <article className="card h-full p-7">
            <p className="t-eyebrow text-ink-48">No invented facts</p>
            <h3 className="t-tagline mt-3">Facts come from code, not guesses.</h3>
            <p className="t-caption mt-2 text-ink-80">
              Readings and manual steps are picked by rules. AI only phrases a sentence from them, and if it's slow you
              get the manual's own words instead.
            </p>
          </article>
        </Reveal>
      </div>
    </section>
  );
}

const PROMISES = [
  { icon: Lock, text: "Your SmartThings login is encrypted before it's stored." },
  { icon: ShieldCheck, text: "Row-level security: your home is readable by you alone." },
  { icon: KeyRound, text: "Devices only change after you confirm, every time." },
  { icon: Trash, text: "Delete your account and everything linked to it, any time." },
];

export function Privacy() {
  return (
    <section id="privacy" className="scroll-mt-28 px-4 py-16 sm:px-8 sm:py-20" aria-labelledby="privacy-title">
      <SectionHead id="privacy-title" eyebrow="Privacy" title="Your home stays yours." />
      <Reveal className="mx-auto mt-12 max-w-[900px]">
        <ul className="card grid gap-px overflow-hidden sm:grid-cols-2">
          {PROMISES.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-start gap-3 p-6">
              <Icon size={20} className="mt-0.5 shrink-0" aria-hidden="true" />
              <p className="t-caption text-ink-80">{text}</p>
            </li>
          ))}
        </ul>
        <p className="t-fine mt-4 text-center text-ink-48">
          Speech is recognised by your browser's speech service. We don't keep your questions after a session ends.
        </p>
      </Reveal>
    </section>
  );
}

export function CallToAction() {
  return (
    <section className="px-4 pb-24 pt-10" aria-labelledby="cta-title">
      <Reveal className="tile-dark mx-auto max-w-[1100px] p-8 text-center sm:p-14">
        <h2 id="cta-title" className="t-display">
          See it answer in 20 seconds.
        </h2>
        <p className="t-body mx-auto mt-4 max-w-[520px] text-white/70">
          Break the demo washer, ask why, change your mind halfway. Then connect your own home.
        </p>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <Link to="/demo" className="btn-pill !bg-white !text-ink">
            <CirclePlay size={17} aria-hidden="true" /> Try the live demo
          </Link>
          <Link to="/signup" className="btn-pill-ghost !border-white/25 !bg-white/10 !text-white">
            Create an account <ArrowRight size={17} aria-hidden="true" />
          </Link>
        </div>
      </Reveal>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="px-4 pb-10">
      <div className="glass mx-auto flex max-w-[1180px] flex-col items-center gap-4 rounded-lg px-6 py-5 sm:flex-row">
        <Logo />
        <p className="t-fine text-ink-48 sm:ml-4">© 2026 PROCASTO-AI</p>
        <nav aria-label="Footer" className="flex gap-5 t-caption text-ink-80 sm:ml-auto">
          <Link to="/demo" className="hover:text-ink">Demo</Link>
          <Link to="/login" className="hover:text-ink">Sign in</Link>
          <a href="#privacy" className="hover:text-ink">Privacy</a>
        </nav>
      </div>
    </footer>
  );
}
