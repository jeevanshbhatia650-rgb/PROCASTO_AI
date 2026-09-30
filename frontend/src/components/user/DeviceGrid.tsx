import { useStore } from "../../lib/store";
import { DeviceCard } from "./DeviceCard";
import { useShell } from "../../pages/app/shell";

const ORDER = ["washer", "dryer", "ac"];

/** F1: the home, live. */
export function DeviceGrid() {
  const { mode } = useShell();
  const devices = useStore((s) => s.devices);
  const list = Object.values(devices).sort((a, b) => (ORDER.indexOf(a.info.kind) + 4) % 4 - (ORDER.indexOf(b.info.kind) + 4) % 4);
  if (list.length === 0) {
    return <p className="t-caption text-ink-48">Connecting to your home…</p>;
  }
  const cards = <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">{list.map((snapshot) => <DeviceCard key={snapshot.info.device_id} snapshot={snapshot} />)}</div>;
  return mode === "demo" ? <section aria-label="Devices">{cards}</section> : <details className="card mb-5 p-4" aria-label="Devices"><summary className="cursor-pointer t-caption-strong">{list.length} devices available to ask about</summary><div className="mt-4">{cards}</div></details>;
}
