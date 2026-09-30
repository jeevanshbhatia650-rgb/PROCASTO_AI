import { Grid2X2, House, Mic, Sparkles, UserRound } from "lucide-react";
import { NavLink, useNavigate } from "react-router";
import { useShell } from "./shell";

type Item = { to: string; label: string; icon: typeof House; end?: boolean };

/** The dark pill at the bottom, as in the reference. Labels say what's there, not vague umbrellas. */
export function BottomNav() {
  const { mode, base } = useShell();
  const navigate = useNavigate();
  const items: Item[] = [
    { to: base, label: "Home", icon: House, end: true },
    { to: `${base}/assistant`, label: "Assistant", icon: Sparkles },
    ...(mode === "account"
      ? [
          { to: "/app/integrations", label: "Devices", icon: Grid2X2 },
          { to: "/app/profile", label: "Profile", icon: UserRound },
        ]
      : [{ to: "/signup", label: "Sign up", icon: UserRound }]),
  ];

  return (
    <nav
      aria-label="App"
      className="fixed inset-x-0 bottom-0 z-40 flex justify-center px-3 pb-[max(12px,env(safe-area-inset-bottom))]"
    >
      <div className="glass-dark flex items-center gap-1 rounded-full p-1.5">
        {items.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `pressable flex items-center gap-2 rounded-full px-3.5 py-2.5 t-caption transition-colors duration-150 sm:px-4 ${
                isActive ? "bg-white/[0.16] text-white" : "text-white/60 hover:text-white"
              }`
            }
          >
            <Icon size={18} aria-hidden="true" />
            <span className="hidden sm:inline">{label}</span>
            <span className="sr-only sm:hidden">{label}</span>
          </NavLink>
        ))}
        <button
          type="button"
          onClick={() => navigate(`${base}/assistant?listen=1`)}
          className="pressable ml-1 grid h-10 w-10 place-items-center rounded-full bg-white text-ink"
          aria-label="Ask a question"
          title="Ask a question"
        >
          <Mic size={18} aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}
