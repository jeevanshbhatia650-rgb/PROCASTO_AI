import { useEffect, useRef, type ReactNode } from "react";

/**
 * Fades a block up the first time it scrolls into view. Visible by default: only blocks that start below the fold
 * are hidden, and only once JavaScript is running, so crawlers, previews and no-JS readers always see everything.
 */
export function Reveal({ children, className = "", delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || !("IntersectionObserver" in window)) return;
    if (el.getBoundingClientRect().top < window.innerHeight) return; // already on screen: never hide it
    el.classList.add("reveal-hidden");
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          el.classList.remove("reveal-hidden");
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -60px 0px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className={`reveal ${className}`} style={delay ? { transitionDelay: `${delay}ms` } : undefined}>
      {children}
    </div>
  );
}
