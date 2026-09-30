import { ArrowRight, CirclePlay } from "lucide-react";
import { Link } from "react-router";
import { Backdrop } from "../../components/glass/Backdrop";
import { Logo } from "../../components/glass/Logo";
import { HeroPreview } from "./HeroPreview";
import { CallToAction, Different, Footer, HowItWorks, Privacy } from "./LandingSections";

const SECTIONS = [
  ["#how", "How it works"],
  ["#different", "What's different"],
  ["#privacy", "Privacy"],
] as const;

function Nav() {
  return (
    <header className="fixed inset-x-0 top-0 z-30 px-3 pt-3 sm:px-6 sm:pt-4">
      <nav
        aria-label="Main"
        className="glass mx-auto flex max-w-[1180px] items-center gap-2 rounded-full !bg-white/80 py-2 pl-4 pr-2 sm:gap-4 sm:pl-5"
      >
        <Logo />
        <ul className="mx-auto hidden items-center gap-1 md:flex">
          {SECTIONS.map(([href, label]) => (
            <li key={href}>
              <a
                href={href}
                className="rounded-full px-3.5 py-2 t-caption text-ink-80 transition-colors duration-150 hover:bg-white/70 hover:text-ink"
              >
                {label}
              </a>
            </li>
          ))}
        </ul>
        <Link to="/login" className="ml-auto rounded-full px-3 py-2 t-caption-strong text-ink-80 hover:text-ink md:ml-0">
          Sign in
        </Link>
        <Link to="/signup" className="btn-pill !px-4 !py-2 !text-[14px]">
          Get started
        </Link>
      </nav>
    </header>
  );
}

function Hero() {
  return (
    <section className="px-4 pb-16 pt-32 sm:pt-40" aria-labelledby="hero-title">
      <div className="mx-auto max-w-[900px] text-center">
        <p className="rise glass mx-auto inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 t-fine text-ink-80">
          <span className="h-1.5 w-1.5 rounded-full bg-ok" aria-hidden="true" />
          Works with Samsung SmartThings
        </p>
        <h1 id="hero-title" className="rise t-hero mt-6" style={{ animationDelay: "60ms" }}>
          Your home, explained.
        </h1>
        <p className="rise t-body mx-auto mt-6 max-w-[620px] text-[18px] text-ink-80" style={{ animationDelay: "120ms" }}>
          Ask about any appliance out loud. PROCASTO reads its live state, checks the manual for your exact model, and
          answers with the page it came from, usually before you finish the question.
        </p>
        <div className="rise mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row" style={{ animationDelay: "180ms" }}>
          <Link to="/signup" className="btn-pill w-full sm:w-auto">
            Get started <ArrowRight size={17} aria-hidden="true" />
          </Link>
          <Link to="/demo" className="btn-pill-ghost w-full sm:w-auto">
            <CirclePlay size={17} aria-hidden="true" /> Try the live demo
          </Link>
        </div>
        <p className="rise t-fine mt-4 text-ink-48" style={{ animationDelay: "220ms" }}>
          The demo needs no account. It runs on a simulated home you can break.
        </p>
      </div>
      <div className="rise mt-14 sm:mt-16" style={{ animationDelay: "260ms" }}>
        <HeroPreview />
      </div>
    </section>
  );
}

export default function Landing() {
  return (
    <>
      <Backdrop />
      <Nav />
      <main>
        <Hero />
        {/* One frosted panel for everything below the hero, as in the reference: text never sits on the room. */}
        <div className="px-3 sm:px-6">
          <div className="glass-panel mx-auto max-w-[1240px] rounded-xl">
            <HowItWorks />
            <Different />
            <Privacy />
          </div>
        </div>
        <CallToAction />
      </main>
      <Footer />
    </>
  );
}
