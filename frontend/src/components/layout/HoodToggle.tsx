import { useStore } from "../../lib/store";

/** F21: clean view ↔ engine view. */
export function HoodToggle() {
  const open = useStore((s) => s.hoodOpen);
  const setHood = useStore((s) => s.setHood);
  return (
    <button
      type="button"
      role="switch"
      aria-checked={open}
      aria-label="Under the hood"
      onClick={() => setHood(!open)}
      className="group flex items-center gap-2.5 t-caption text-ink-80"
    >
      <span aria-hidden="true">Under the hood</span>
      <span
        className={`relative inline-flex h-[26px] w-[44px] shrink-0 items-center rounded-full transition-colors duration-200 ${
          open ? "bg-primary" : "bg-chip"
        }`}
      >
        <span
          className="absolute left-[3px] h-5 w-5 rounded-full bg-white shadow-[0_1px_3px_rgba(0,0,0,0.25)] transition-transform duration-200 ease-out group-active:scale-95"
          style={{ transform: open ? "translateX(18px)" : "translateX(0)" }}
        />
      </span>
    </button>
  );
}
