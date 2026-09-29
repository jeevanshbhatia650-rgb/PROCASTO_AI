import type { DeviceSnapshot, ParkedPlan } from "../types/generated";

const SPIKE_W = 2500;
const MAX = 3;

/** Questions worth asking right now, read from the live state of the home. */
export function suggestions(devices: DeviceSnapshot[], parked: ParkedPlan[]): string[] {
  const out: string[] = [];
  const name = (id: string) => devices.find((d) => d.info.device_id === id)?.info.display_name.toLowerCase() ?? id;
  for (const d of devices) {
    const code = d.attributes.error_code as string | null | undefined;
    if (code) out.push(`What does ${code} mean on the ${d.info.display_name.toLowerCase()}?`);
  }
  for (const d of devices) {
    const power = d.attributes.power_w as number | undefined;
    if (d.info.kind === "ac" && power != null && power > SPIKE_W) out.push("Why is the AC using so much power?");
  }
  const top = parked[0];
  if (top?.device_ids[0]) out.push(`Go back to the ${name(top.device_ids[0])}`);
  for (const d of devices) {
    if (d.attributes.state === "RUNNING") out.push(`How long until the ${d.info.display_name.toLowerCase()} finishes?`);
  }
  out.push("Is the dryer done?", "Set the AC to 24 degrees");
  return [...new Set(out)].slice(0, MAX);
}
