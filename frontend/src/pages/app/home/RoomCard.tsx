import { ArrowUpRight, ChevronRight } from "lucide-react";
import { Link } from "react-router";
import { DeviceIcon } from "../../../components/icons";
import { deviceView, type Tone } from "../../../lib/deviceView";
import type { DeviceSnapshot } from "../../../types/generated";
import { askLink, questionFor } from "./questions";

const DOT: Record<Tone, string> = { ok: "bg-ok", run: "bg-ok", warn: "bg-run", bad: "bg-bad-dark", off: "bg-off" };

export function RoomCard({ room, devices, base }: { room: string; devices: DeviceSnapshot[]; base: string }) {
  return <section className="card p-5 sm:p-7" aria-label={room}>
    <div className="flex items-start justify-between gap-3"><div><h2 className="t-section">{room}</h2><p className="t-caption mt-1 text-ink-48">{devices.length} device{devices.length === 1 ? "" : "s"}</p></div><span className="rounded-full bg-ink/[0.04] p-2.5"><ChevronRight size={18} className="text-ink-48" aria-hidden="true" /></span></div>
    {devices.length ? <ul className="mt-6 space-y-2.5">{devices.map((device) => { const view = deviceView(device); return <li key={device.info.device_id}><Link to={askLink(base, questionFor(device))} className="pressable flex min-h-20 items-center gap-4 rounded-lg border border-ink/[0.06] bg-white/70 p-3 hover:bg-white"><span className="grid h-12 w-12 shrink-0 place-items-center rounded-md bg-ink/[0.05] text-ink-80"><DeviceIcon kind={device.info.kind} size={23} /></span><span className="min-w-0 flex-1"><span className="block truncate t-caption-strong">{device.info.display_name}</span><span className="mt-1 flex items-center gap-1.5 t-fine text-ink-48"><span className={`h-1.5 w-1.5 shrink-0 rounded-full ${DOT[view.tone]}`} aria-hidden="true" /><span className="truncate">{view.status === "No live state yet" ? view.value : `${view.value} · ${view.status}`}</span></span></span><ArrowUpRight size={17} className="shrink-0 text-ink-48" aria-hidden="true" /></Link></li>; })}</ul> : <p className="mt-10 t-caption text-ink-48">No devices in this room yet.</p>}
  </section>;
}
