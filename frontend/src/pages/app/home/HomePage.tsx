import { Bell, ChevronRight, CircleCheck, Grid2X2, LoaderCircle, Mic2, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { deviceView, needsAttention } from "../../../lib/deviceView";
import { useStore } from "../../../lib/store";
import { useWatchlist } from "../../../lib/watchlist";
import type { DeviceSnapshot } from "../../../types/generated";
import { useShell } from "../shell";
import { SimulateCard } from "../SimulateControls";
import { EnergyCard } from "./EnergyCard";
import { RoomCard } from "./RoomCard";

function byRoom(devices: DeviceSnapshot[]): [string, DeviceSnapshot[]][] {
  const rooms = new Map<string, DeviceSnapshot[]>();
  for (const d of devices) rooms.set(d.info.room, [...(rooms.get(d.info.room) ?? []), d]);
  return [...rooms.entries()];
}

/** A quiet first glance: count everything, then focus on one room and the next useful action. */
export default function HomePage() {
  const { mode, base } = useShell();
  const hello = useStore((s) => s.hello);
  const devices = Object.values(useStore((s) => s.devices));
  const [chosen, setChosen] = useState<string | null>(null);
  const { watched, toggleMany } = useWatchlist(devices.map((d) => d.info.device_id));
  const rooms = byRoom(devices);
  const selected = chosen === "all" ? "all" : rooms.some(([name]) => name === chosen) ? chosen : rooms[0]?.[0];
  const showing = selected === "all" ? devices : (rooms.find(([name]) => name === selected)?.[1] ?? []);
  const watchedHere = showing.length > 0 && showing.every((d) => watched.has(d.info.device_id));
  const attention = devices.filter(needsAttention);
  const latest = devices.filter((d) => watched.has(d.info.device_id)).sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0];
  const live = hello?.home === "smartthings";

  if (!hello) return <p className="flex items-center justify-center gap-2 py-24 t-caption text-ink-80" role="status"><LoaderCircle size={17} className="animate-spin" aria-hidden="true" /> Loading your home…</p>;

  return <div className="space-y-5 sm:space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-3 px-1">
      <div><p className="t-eyebrow text-ink-48">{live ? "SMARTTHINGS HOME" : "A SMALL PREVIEW"}</p><h2 className="t-display mt-1">Your home</h2>
        <p className="t-caption mt-1 text-ink-48">{devices.length} {live ? "connected" : "simulated"} device{devices.length === 1 ? "" : "s"}{live && " · Everything shared with PROCASTO"}</p></div>
      <span className="inline-flex items-center gap-2 rounded-full bg-white/70 px-3 py-2 t-fine text-ink-80"><span className={`h-2 w-2 rounded-full ${live ? "bg-ok" : "bg-run"}`} aria-hidden="true" />{live ? "Live from SmartThings" : "Demo devices"}</span>
    </div>
    {hello.notice && <p className="rounded-lg bg-run/10 px-4 py-3 t-caption text-run-text" role="status">{hello.notice}</p>}
    {!live && mode === "account" && <Link to="/app/integrations" className="card pressable flex items-center justify-between gap-4 p-5 hover:bg-white/90"><span><span className="t-caption-strong">Bring in your real home</span><span className="mt-1 block t-fine text-ink-48">Connect once with Samsung to see the devices you share.</span></span><ChevronRight size={20} className="shrink-0" aria-hidden="true" /></Link>}
    {rooms.length > 0 && <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1" role="group" aria-label="Choose a room">
      {rooms.map(([name, list]) => <button key={name} type="button" onClick={() => setChosen(name)} aria-pressed={selected === name} className={`pressable shrink-0 rounded-full px-4 py-2.5 t-caption ${selected === name ? "bg-white text-ink shadow-sm" : "bg-ink/[0.05] text-ink-80 hover:bg-white/70"}`}>{name} <span className="ml-1 text-ink-48">{list.length}</span></button>)}
      {rooms.length > 1 && <button type="button" onClick={() => setChosen("all")} aria-pressed={selected === "all"} className={`pressable inline-flex shrink-0 items-center gap-1.5 rounded-full px-4 py-2.5 t-caption ${selected === "all" ? "bg-white text-ink shadow-sm" : "bg-ink/[0.05] text-ink-80 hover:bg-white/70"}`}><Grid2X2 size={15} aria-hidden="true" /> All rooms</button>}
    </div>}
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="grid grid-cols-1 content-start gap-4">
        <RoomCard room={selected === "all" ? "All rooms" : selected ?? "My home"} devices={showing} base={base} />
        <EnergyCard />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-1 lg:content-start">
        <section className="card p-5 sm:p-6" aria-label="Live update focus"><span className="grid h-11 w-11 place-items-center rounded-full bg-ok/12 text-ok-text"><Bell size={20} aria-hidden="true" /></span>
          <h3 className="t-tagline mt-4">Choose live updates</h3><p className="t-caption mt-1 text-ink-80">Follow what matters in this room. Every device stays available to ask about.</p>
          <button type="button" role="switch" aria-checked={watchedHere} disabled={!showing.length} onClick={() => void toggleMany(showing.map((d) => d.info.device_id), !watchedHere)} className="pressable mt-5 flex w-full items-center justify-between rounded-full bg-ink/[0.04] px-4 py-2.5 t-caption-strong">Watch this {selected === "all" ? "home" : "room"}<span className={`relative h-6 w-11 rounded-full transition-colors ${watchedHere ? "bg-ok" : "bg-ink/15"}`} aria-hidden="true"><span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${watchedHere ? "translate-x-5" : "translate-x-0.5"}`} /></span></button>
          <Link to={mode === "account" ? "/app/integrations" : `${base}/assistant`} className="mt-3 inline-flex items-center gap-1 t-fine text-ink-80 hover:text-ink">{mode === "account" ? "Choose individual devices" : "Try the assistant"}<ChevronRight size={14} aria-hidden="true" /></Link>
        </section>
        <Link to={`${base}/assistant`} className="glass-dark pressable flex items-center justify-between gap-3 rounded-lg px-5 py-4 t-caption-strong text-white"><span className="inline-flex items-center gap-3"><Mic2 size={19} aria-hidden="true" /> Ask about this room</span><ChevronRight size={18} aria-hidden="true" /></Link>
        <section className="card p-5 sm:col-span-2 lg:col-span-1" aria-label="Home insight"><p className="t-eyebrow text-ink-48">WORTH KNOWING · LIVE</p><div className="mt-3 flex items-start gap-3">{attention.length ? <TriangleAlert size={20} className="shrink-0 text-bad-text" aria-hidden="true" /> : <CircleCheck size={20} className="shrink-0 text-ok" aria-hidden="true" />}<div><p className="t-caption-strong">{attention.length ? `${attention.length} ${attention.length === 1 ? "device needs" : "devices need"} attention` : latest ? `${latest.info.display_name} · ${deviceView(latest).value}` : "Nothing followed yet"}</p><p className="t-fine mt-1 text-ink-48">{attention.length ? attention.map((d) => d.info.display_name).join(", ") : latest ? deviceView(latest).status : "Choose a room to focus its live updates."}</p></div></div></section>
      </div>
    </div>
    {mode === "demo" && <details className="t-fine text-ink-48"><summary className="cursor-pointer px-1 py-2">Demo controls</summary><SimulateCard /></details>}
  </div>;
}
