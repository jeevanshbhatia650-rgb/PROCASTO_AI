import { MotionConfig } from "motion/react";
import { useEffect, useMemo, useRef } from "react";
import { Link, Outlet, useLocation, useMatches, useNavigate } from "react-router";
import { Toaster, toast } from "sonner";
import { ErrorBoundary } from "../../components/ErrorBoundary";
import { Backdrop } from "../../components/glass/Backdrop";
import { signOut, useProfile } from "../../lib/account";
import { SCENARIOS, triggerScenario } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { alertText } from "../../lib/deviceView";
import { POWER_SAMPLE_MS, useStore } from "../../lib/store";
import { freshToken } from "../../lib/supabase";
import { useWatchlist } from "../../lib/watchlist";
import { socket } from "../../lib/ws";
import { AccountMenu } from "./AccountMenu";
import { BottomNav } from "./BottomNav";
import { ConnectWindow } from "./ConnectWindow";
import { askLink, questionFor } from "./home/questions";
import { ShellContext, useShell, type ShellMode } from "./shell";
import { SimulateRail } from "./SimulateControls";

function usePageTitle(): string {
  const matches = useMatches();
  const titles = matches.map((m) => (m.handle as { title?: string } | undefined)?.title).filter(Boolean);
  return titles.at(-1) ?? "Home";
}

/** One socket per visit. Signed-in visits authenticate with a fresh token; an expired one sends you to sign in. */
function useHomeSocket(mode: ShellMode): void {
  const navigate = useNavigate();
  useEffect(() => {
    const token = mode === "account" ? (refresh: boolean) => freshToken(refresh ? Infinity : 60) : async () => null;
    socket.start(token, () => {
      void signOut().finally(() => navigate("/login?next=/app", { replace: true }));
    }, mode === "account");
    return () => socket.stop();
  }, [mode, navigate]);
}

function useToasts(): void {
  const message = useStore((s) => s.toast);
  useEffect(() => {
    if (message) toast(message.message);
  }, [message]);
}

/** 1-5 break something in the demo home, from any page. Never while typing. */
function useFaultKeys(): void {
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (e.metaKey || e.ctrlKey || e.altKey || el?.closest("input, textarea, [contenteditable=true]")) return;
      const scenario = SCENARIOS[Number(e.key) - 1];
      if (scenario && useStore.getState().hello?.home === "demo") triggerScenario(scenario.id);
    };
    window.addEventListener("keydown", down);
    return () => window.removeEventListener("keydown", down);
  }, []);
}

/** The home page's power chart ticks on a clock, whether or not a device reports anything new. */
function usePowerClock(): void {
  useEffect(() => {
    const id = setInterval(() => useStore.getState().samplePower(), POWER_SAMPLE_MS);
    return () => clearInterval(id);
  }, []);
}

/** Followed devices speak up: a toast when one changes state or needs you, with the question to ask. */
function WatchAlerts() {
  const { base } = useShell();
  const navigate = useNavigate();
  const session = useStore((s) => s.hello?.session_id);
  const devices = useStore((s) => s.devices);
  const { watched } = useWatchlist(Object.keys(devices));
  const seen = useRef({ session, states: new Map<string, string>() });

  useEffect(() => {
    if (seen.current.session !== session) seen.current = { session, states: new Map() }; // a new home isn't news
    const states = seen.current.states;
    for (const device of Object.values(devices)) {
      const id = device.info.device_id;
      const before = states.get(id);
      const now = alertText(device);
      states.set(id, now);
      if (before === undefined || before === now || !watched.has(id)) continue;
      const question = questionFor(device);
      // One slot per device: a newer alert replaces the older one instead of stacking.
      toast(now, { id: `watch-${id}`, action: { label: "Ask", onClick: () => navigate(askLink(base, question)) } });
    }
  }, [session, devices, watched, base, navigate]);
  return null;
}

function useProfileLoad(mode: ShellMode): void {
  const auth = useAuth();
  const load = useProfile((s) => s.load);
  const userId = auth.status === "signed_in" ? auth.session.user.id : null;
  useEffect(() => {
    if (mode === "account" && userId) void load(userId);
  }, [mode, userId, load]);
}

function HomeBadge() {
  const connection = useStore((s) => s.connection);
  const hello = useStore((s) => s.hello);
  const live = connection === "open" && hello;
  const label = !live ? "Connecting…" : hello.home === "smartthings" ? "SmartThings · live" : "Demo home";
  const dot = !live ? "bg-run" : hello.notice ? "bg-run" : "bg-ok";
  return (
    <p className="glass inline-flex items-center gap-2 rounded-full px-3 py-1.5 t-fine text-ink-80" role="status" title={hello?.notice || undefined}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden="true" />
      {label}
    </p>
  );
}

function DemoActions() {
  return (
    <div className="flex items-center gap-2">
      <Link to="/login" className="hidden rounded-full px-3 py-2 t-caption-strong text-ink-80 hover:text-ink sm:inline">
        Sign in
      </Link>
      <Link to="/signup" className="btn-pill !px-4 !py-2 !text-[14px]">
        Create account
      </Link>
    </div>
  );
}

export default function AppShell({ mode }: { mode: ShellMode }) {
  const title = usePageTitle();
  const { pathname } = useLocation(); // a page that crashed gets a clean start when you move on
  const shell = useMemo(() => ({ mode, base: mode === "account" ? ("/app" as const) : ("/demo" as const) }), [mode]);
  useHomeSocket(mode);
  useProfileLoad(mode);
  useToasts();
  useFaultKeys();
  usePowerClock();

  return (
    <ShellContext.Provider value={shell}>
      <MotionConfig reducedMotion="user">
        <Backdrop />
        <SimulateRail />
        <div className="min-h-dvh px-2.5 pb-32 pt-2.5 sm:px-5 sm:pt-5 lg:pl-24">
          <div className="glass-panel mx-auto max-w-[1360px] rounded-xl p-3.5 sm:p-7">
            <header className="grid grid-cols-[1fr_auto] items-center gap-3 pb-5 sm:pb-7 lg:grid-cols-[1fr_auto_1fr]">
              <div className="order-2 col-span-2 lg:order-none lg:col-span-1">
                <HomeBadge />
              </div>
              <h1 className="t-title order-1 lg:order-none lg:text-center">{title}</h1>
              <div className="order-1 flex justify-end lg:order-none">{mode === "account" ? <AccountMenu /> : <DemoActions />}</div>
            </header>
            <ErrorBoundary key={pathname} name="page">
              <Outlet />
            </ErrorBoundary>
          </div>
        </div>
        <BottomNav />
        {mode === "account" && <ConnectWindow />}
        <WatchAlerts />
        <Toaster position="top-center" offset={16} toastOptions={{ className: "t-caption" }} />
      </MotionConfig>
    </ShellContext.Provider>
  );
}
