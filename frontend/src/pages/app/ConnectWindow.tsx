import { Check, LoaderCircle, PlugZap, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import { friendlyError, useProfile } from "../../lib/account";
import { useAuth } from "../../lib/auth";
import { connectSmartThings } from "../../lib/connections";
import { useSiteConfig } from "./shell";

const READS = ["The devices you approve at Samsung", "Available live status and error codes"];
const NEVER = ["Change a device without your OK", "Share your home with anyone"];

/**
 * The first thing a new account sees: a small window asking to connect Samsung SmartThings.
 * A native <dialog>, so focus stays inside, Escape closes it, and the page behind is inert.
 */
export function ConnectWindow() {
  const auth = useAuth();
  const userId = auth.status === "signed_in" ? auth.session.user.id : null;
  const profile = useProfile((s) => s.profile);
  const save = useProfile((s) => s.save);
  const config = useSiteConfig();
  const [params] = useSearchParams();
  const dialog = useRef<HTMLDialogElement>(null);
  const [dismissed, setDismissed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const shouldOpen = !!userId && !!profile && !profile.onboarded && !params.has("smartthings") && !dismissed;
  const available = config?.smartthings === true;

  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (shouldOpen && !el.open) el.showModal();
    if (!shouldOpen && el.open) el.close();
  }, [shouldOpen]);

  const later = () => {
    setDismissed(true);
    if (userId) void save(userId, { onboarded: true }).catch(() => {}); // if this fails, the window simply returns
  };

  const connect = async () => {
    setBusy(true);
    setError(null);
    try {
      if (userId) await save(userId, { onboarded: true });
      await connectSmartThings(); // leaves for Samsung's login page
    } catch (err) {
      setError(friendlyError(err));
      setBusy(false);
    }
  };

  return (
    <dialog
      ref={dialog}
      aria-labelledby="connect-title"
      onCancel={(event) => {
        event.preventDefault();
        later();
      }}
      className="m-auto w-[min(540px,calc(100%-24px))] overflow-visible bg-transparent p-0 text-ink backdrop:bg-black/30 backdrop:backdrop-blur-[3px]"
    >
      <div className="glass window-enter relative rounded-xl p-7 sm:p-9">
        <button
          type="button"
          onClick={later}
          className="pressable absolute right-4 top-4 grid h-9 w-9 place-items-center rounded-full text-ink-48 hover:bg-white/80 hover:text-ink"
          aria-label="Not now"
        >
          <X size={18} aria-hidden="true" />
        </button>
        <span className="grid h-12 w-12 place-items-center rounded-full bg-ink text-white">
          <PlugZap size={22} aria-hidden="true" />
        </span>
        <h2 id="connect-title" className="t-display mt-5 pr-8">
          Connect your Samsung account
        </h2>
        <p className="t-body mt-3 text-ink-80">
          One approval at Samsung brings your shared SmartThings devices into PROCASTO. No setup is needed for each device.
        </p>
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <List title="We read" items={READS} />
          <List title="We never" items={NEVER} />
        </div>
        {error && (
          <p role="alert" className="mt-5 rounded-md bg-bad/10 px-4 py-3 t-caption text-bad-text">
            {error}
          </p>
        )}
        <div className="mt-7 flex flex-col gap-2.5">
          <button type="button" className="btn-pill w-full" onClick={() => void connect()} disabled={!available || busy}>
            {busy && <LoaderCircle size={17} className="animate-spin" aria-hidden="true" />}
            Connect SmartThings
          </button>
          {!available && (
            <p className="t-fine text-center text-ink-48">
              SmartThings isn't set up on this server yet, so the demo home stands in until it is.
            </p>
          )}
          <button type="button" className="btn-pill-ghost w-full" onClick={later}>
            Use the demo home for now
          </button>
        </div>
        <p className="t-fine mt-4 text-center text-ink-48">You can connect any time from Devices.</p>
      </div>
    </dialog>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-lg bg-white/60 p-4">
      <p className="t-eyebrow text-ink-48">{title}</p>
      <ul className="mt-2 space-y-1.5">
        {items.map((item) => (
          <li key={item} className="flex items-start gap-2 t-caption text-ink-80">
            <Check size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
