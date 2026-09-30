import { Bot, CircleCheck, House, LoaderCircle, PlugZap, Radio, TriangleAlert, Unplug, WandSparkles } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router";
import { toast } from "sonner";
import { friendlyError, useProfile } from "../../lib/account";
import { useAuth } from "../../lib/auth";
import {
  connectSmartThings,
  disconnectSmartThings,
  listConnections,
  smartthingsResult,
  type Connection,
} from "../../lib/connections";
import { useStore } from "../../lib/store";
import { useWatchlist } from "../../lib/watchlist";
import { DeviceIcon } from "../../components/icons";
import { socket } from "../../lib/ws";
import { useSiteConfig } from "./shell";

function Badge({ tone, children }: { tone: "ok" | "muted" | "warn"; children: ReactNode }) {
  const style = { ok: "bg-ok/12 text-ok-text", muted: "bg-ink/[0.06] text-ink-80", warn: "bg-run/15 text-run-text" }[tone];
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 t-fine ${style}`}>{children}</span>;
}

function Tile({ icon, title, badge, children }: { icon: ReactNode; title: string; badge: ReactNode; children: ReactNode }) {
  return (
    <section className="card flex h-full flex-col p-6" aria-label={title}>
      <div className="flex items-start gap-4">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-ink text-white">{icon}</span>
        <div className="min-w-0 flex-1">
          <h2 className="t-tagline">{title}</h2>
          <div className="mt-1.5">{badge}</div>
        </div>
      </div>
      <div className="mt-5 flex flex-1 flex-col">{children}</div>
    </section>
  );
}

/** undefined while checking; "error" when the check failed, so we never offer Connect on a guess. */
type ConnectionState = Connection | null | undefined | "error";

function SmartThingsTile({ state, refresh }: { state: ConnectionState; refresh: () => void }) {
  const config = useSiteConfig();
  const notice = useStore((s) => s.hello?.notice);
  const [busy, setBusy] = useState<null | "connect" | "disconnect">(null);
  const [confirming, setConfirming] = useState(false);
  const available = config?.smartthings === true;
  const connection = state === "error" ? undefined : state;

  const connect = async () => {
    setBusy("connect");
    try {
      await connectSmartThings();
    } catch (err) {
      toast.error(friendlyError(err));
      setBusy(null);
    }
  };
  const disconnect = async () => {
    setBusy("disconnect");
    try {
      await disconnectSmartThings();
      socket.restart(); // back to the demo home
      toast("SmartThings disconnected. Your saved login was deleted.");
      refresh();
    } catch (err) {
      toast.error(friendlyError(err));
    } finally {
      setBusy(null);
      setConfirming(false);
    }
  };

  let badge = <Badge tone="muted">Not connected</Badge>;
  if (state === "error") badge = <Badge tone="warn">Couldn't check</Badge>;
  else if (connection === undefined) badge = <Badge tone="muted">Checking…</Badge>;
  else if (connection) badge = <Badge tone="ok"><Radio size={13} aria-hidden="true" /> Connected · {connection.account_label || "Samsung account"}</Badge>;
  else if (!available) badge = <Badge tone="warn">Not set up on this server</Badge>;

  return (
    <Tile icon={<PlugZap size={20} aria-hidden="true" />} title="Samsung SmartThings" badge={badge}>
      <p className="t-caption text-ink-80">
        Connect once through Samsung. Every device you approve appears here; supported readings update live.
      </p>
      <ul className="mt-4 space-y-1.5 t-caption text-ink-80">
        <li className="flex gap-2"><CircleCheck size={16} className="mt-0.5 shrink-0" aria-hidden="true" /> Reads each device's available status and capabilities</li>
        <li className="flex gap-2"><CircleCheck size={16} className="mt-0.5 shrink-0" aria-hidden="true" /> Changes a device only after you confirm</li>
        <li className="flex gap-2"><CircleCheck size={16} className="mt-0.5 shrink-0" aria-hidden="true" /> Your login is encrypted before it's stored</li>
      </ul>
      {connection && notice && (
        <p className="mt-4 flex gap-2 rounded-md bg-run/10 px-4 py-3 t-caption text-run-text">
          <TriangleAlert size={16} className="mt-0.5 shrink-0" aria-hidden="true" /> {notice}
        </p>
      )}
      <div className="mt-auto flex flex-wrap gap-2 pt-6">
        {connection ? (
          confirming ? (
            <>
              <p className="w-full t-caption text-ink-80">Disconnect? Your home returns to a small, clearly labelled demo.</p>
              <button type="button" className="btn-pill !bg-bad" onClick={() => void disconnect()} disabled={busy !== null}>
                {busy === "disconnect" && <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />} Disconnect
              </button>
              <button type="button" className="btn-pill-ghost" onClick={() => setConfirming(false)}>Keep it</button>
            </>
          ) : (
            <button type="button" className="btn-pill-ghost" onClick={() => setConfirming(true)}>
              <Unplug size={16} aria-hidden="true" /> Disconnect
            </button>
          )
        ) : state === "error" ? (
          <button type="button" className="btn-pill-ghost" onClick={refresh}>Check again</button>
        ) : (
          <button type="button" className="btn-pill" onClick={() => void connect()} disabled={!available || busy !== null || connection === undefined}>
            {busy === "connect" && <LoaderCircle size={16} className="animate-spin" aria-hidden="true" />} Connect SmartThings
          </button>
        )}
      </div>
      {connection === null && !available && (
        <p className="t-fine mt-3 text-ink-48">The server needs SmartThings app credentials first. Until then the demo home stands in.</p>
      )}
    </Tile>
  );
}

function DeviceChoices() {
  const hello = useStore((s) => s.hello);
  const devices = Object.values(useStore((s) => s.devices));
  const { watched, toggleMany } = useWatchlist(devices.map((d) => d.info.device_id));
  if (hello?.home !== "smartthings") return null;
  return <section className="card p-5 sm:p-6" aria-label="Connected devices">
    <div className="flex flex-wrap items-end justify-between gap-2"><div><h2 className="t-tagline">Your connected devices</h2><p className="t-caption mt-1 text-ink-48">{devices.length} shared from Samsung · {devices.filter((d) => watched.has(d.info.device_id)).length} followed for in-app updates</p></div><span className="rounded-full bg-ok/12 px-3 py-1 t-fine text-ok-text">Live</span></div>
    <p className="t-fine mt-3 text-ink-48">Choose what gets highlighted as it changes. You can still ask the Assistant about any connected device.</p>
    <ul className="mt-5 grid gap-2 sm:grid-cols-2">{devices.map((d) => <li key={d.info.device_id} className="flex items-center gap-3 rounded-lg bg-white/70 p-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-ink/[0.05]"><DeviceIcon kind={d.info.kind} size={20} /></span><span className="min-w-0 flex-1"><span className="block truncate t-caption-strong">{d.info.display_name}</span><span className="block truncate t-fine text-ink-48">{d.info.room}</span></span><button type="button" role="switch" aria-label={`Follow ${d.info.display_name} updates`} aria-checked={watched.has(d.info.device_id)} onClick={() => void toggleMany([d.info.device_id], !watched.has(d.info.device_id))} className={`pressable h-6 w-11 rounded-full p-0.5 ${watched.has(d.info.device_id) ? "bg-ok" : "bg-ink/15"}`}><span className={`block h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${watched.has(d.info.device_id) ? "translate-x-5" : ""}`} /></button></li>)}</ul>
  </section>;
}

export default function IntegrationsPage() {
  const auth = useAuth();
  const config = useSiteConfig();
  const save = useProfile((s) => s.save);
  const [params, setParams] = useSearchParams();
  const [result, setResult] = useState(() => smartthingsResult(params.get("smartthings")));
  const [connections, setConnections] = useState<Connection[] | "error" | undefined>(undefined);
  const [version, setVersion] = useState(0);
  const userId = auth.status === "signed_in" ? auth.session.user.id : null;

  useEffect(() => {
    if (params.has("smartthings")) setParams({}, { replace: true });
  }, [params, setParams]);

  useEffect(() => {
    if (result?.ok && userId) void save(userId, { onboarded: true }).catch(() => {});
  }, [result, userId, save]);

  useEffect(() => {
    let alive = true;
    listConnections()
      .then((rows) => alive && setConnections(rows))
      .catch(() => alive && setConnections("error"));
    return () => {
      alive = false;
    };
  }, [version]);

  const smartthings = Array.isArray(connections) ? (connections.find((c) => c.provider === "smartthings") ?? null) : connections;
  const recheck = () => {
    setResult(null); // an old "connected" banner is wrong after a disconnect
    setConnections(undefined);
    setVersion((v) => v + 1);
  };

  return (
    <div className="space-y-4">
      {result && (
        <p role="status" className={`rounded-lg px-5 py-4 t-caption ${result.ok ? "bg-ok/12 text-ok-text" : "bg-run/12 text-run-text"}`}>
          {result.message}
        </p>
      )}
      <SmartThingsTile state={smartthings} refresh={recheck} />
      <DeviceChoices />
      <details className="card p-5"><summary className="cursor-pointer t-caption-strong">More connections and AI settings</summary><div className="mt-4 grid gap-4 lg:grid-cols-3">
          <Tile icon={<Bot size={20} aria-hidden="true" />} title="Amazon Alexa" badge={<Badge tone="muted">Beta · set up by the server owner</Badge>}>
            <p className="t-caption text-ink-80">
              Ask from an Echo: “Alexa, ask PROCASTO what E3 means on the washer.” Alexa sends whole sentences, so there's
              no head start or interrupting on that path.
            </p>
          </Tile>
          <Tile icon={<House size={20} aria-hidden="true" />} title="Home Assistant" badge={<Badge tone="muted">Exploring</Badge>}>
            <p className="t-caption text-ink-80">A possible bridge for people who already run Home Assistant. It is not a one-tap Samsung replacement.</p>
          </Tile>
          <Tile
            icon={<WandSparkles size={20} aria-hidden="true" />}
            title="AI phrasing"
            badge={<Badge tone={config?.llm === "gemini" ? "ok" : "muted"}>{config?.llm === "gemini" ? "Gemini" : "Templates"}</Badge>}
          >
            <p className="t-caption text-ink-80">
              Facts are always picked by rules. {config?.llm === "gemini" ? "Gemini" : "A template"} only phrases the “what to
              do” sentence, and the manual's own words take over if it's slow.
            </p>
          </Tile>
      </div></details>
    </div>
  );
}
