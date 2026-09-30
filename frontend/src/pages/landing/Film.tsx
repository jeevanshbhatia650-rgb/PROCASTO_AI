import { useEffect, useRef } from "react";

/** The short film. It plays muted only while it's on screen, and never on its own for people who asked for less motion. */
export function Film() {
  const video = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const el = video.current;
    const calm = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (!el || calm || typeof IntersectionObserver === "undefined") return;
    const onScreen = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) void el.play().catch(() => {}); // a browser may still refuse; the controls remain
        else el.pause();
      },
      { threshold: 0.5 },
    );
    onScreen.observe(el);
    return () => onScreen.disconnect();
  }, []);

  return (
    <section id="film" className="scroll-mt-28 px-3 pb-10 sm:px-6 sm:pb-14" aria-labelledby="film-title">
      {/* On a frosted panel like the rest of the page, so the heading never sits on the room illustration. */}
      <div className="glass-panel mx-auto max-w-[1240px] rounded-xl px-3 py-10 text-center sm:px-10 sm:py-14">
        <p className="t-eyebrow text-ink-48">The film</p>
        <h2 id="film-title" className="t-display mt-2">
          See it in 90 seconds.
        </h2>
        <div className="mx-auto mt-8 max-w-[1100px] rounded-xl bg-white/70 p-2 shadow-sm">
          <video
            ref={video}
            className="block aspect-video w-full rounded-lg bg-ink"
            src="/media/procasto-film.mp4"
            poster="/media/procasto-film.jpg"
            aria-label="PROCASTO in 90 seconds: connect, follow devices, get an alert, and an answer with its source"
            muted
            loop
            playsInline
            controls
            preload="none"
          />
        </div>
        <p className="t-fine mt-3 text-ink-48">The SmartThings connection in the film is shown with sample devices.</p>
      </div>
    </section>
  );
}
