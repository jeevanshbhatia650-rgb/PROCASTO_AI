import { LogOut, PlugZap, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { signOut, useProfile } from "../../lib/account";
import { useAuth } from "../../lib/auth";
import { initials } from "./shell";

/** The avatar in the corner: who you are, and the ways out. Opens from its trigger, closes on Escape or outside. */
export function AccountMenu() {
  const auth = useAuth();
  const profile = useProfile((s) => s.profile);
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const email = auth.status === "signed_in" ? (auth.session.user.email ?? "") : "";
  const name = profile?.display_name ?? "";

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent) {
        if (event.key !== "Escape") return;
        setOpen(false);
        trigger.current?.focus(); // keyboard users land back where they were
      } else if (!root.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const leave = async () => {
    setOpen(false);
    await signOut();
    navigate("/", { replace: true });
  };

  return (
    <div ref={root} className="relative">
      <button
        ref={trigger}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="account-panel"
        aria-label="Account"
        className="pressable grid h-11 w-11 place-items-center rounded-full bg-ink font-display text-[14px] font-semibold text-white ring-4 ring-white/60"
      >
        {initials(name, email)}
      </button>
      {open && (
        <div id="account-panel" className="glass window-enter absolute right-0 top-[52px] z-50 w-64 origin-top-right rounded-lg p-2">
          <div className="px-3 pb-3 pt-2">
            <p className="t-caption-strong truncate">{name || "Your account"}</p>
            <p className="t-fine truncate text-ink-48">{email}</p>
          </div>
          <div className="h-px bg-hairline" />
          <Link to="/app/profile" onClick={() => setOpen(false)}
                className="mt-1 flex items-center gap-3 rounded-md px-3 py-2.5 t-caption hover:bg-white/80">
            <UserRound size={17} aria-hidden="true" /> Profile
          </Link>
          <Link to="/app/integrations" onClick={() => setOpen(false)}
                className="flex items-center gap-3 rounded-md px-3 py-2.5 t-caption hover:bg-white/80">
            <PlugZap size={17} aria-hidden="true" /> Integrations
          </Link>
          <button type="button" onClick={() => void leave()}
                  className="flex w-full items-center gap-3 rounded-md px-3 py-2.5 t-caption text-bad-text hover:bg-white/80">
            <LogOut size={17} aria-hidden="true" /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}
