import { useStore } from "../../lib/store";
import { DeviceCard } from "./DeviceCard";

const ORDER = ["washer", "dryer", "ac"];

/** F1: the home, live. */
export function DeviceGrid() {
  const devices = useStore((s) => s.devices);
  const list = Object.values(devices).sort((a, b) => ORDER.indexOf(a.info.kind) - ORDER.indexOf(b.info.kind));
  if (list.length === 0) {
    return <p className="t-caption text-ink-48">Connecting to your home…</p>;
  }
  return (
    <section aria-label="Devices" className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {list.map((snapshot) => (
        <DeviceCard key={snapshot.info.device_id} snapshot={snapshot} />
      ))}
    </section>
  );
}
