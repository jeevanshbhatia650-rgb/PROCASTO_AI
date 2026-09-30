import type { DeviceSnapshot, ParkedPlan } from "../types/generated";
import { SPIKE_W, spokenName } from "./deviceView";

const MAX = 3;

/** Questions worth asking right now, read from the live state of the home. */
export function suggestions(devices: DeviceSnapshot[], parked: ParkedPlan[]): string[] {
  const out: string[] = [];
  const said = (d: DeviceSnapshot) => spokenName(d.info.display_name);
  const name = (id: string) => {
    const device = devices.find((d) => d.info.device_id === id);
    return device ? said(device) : id;
  };
  for (const d of devices) {
    const code = d.attributes.error_code as string | null | undefined;
    if (code) out.push(`What does ${code} mean on the ${said(d)}?`);
  }
  for (const d of devices) {
    const power = d.attributes.power_w as number | undefined;
    if (d.info.kind === "ac" && power != null && power > SPIKE_W) out.push("Why is the AC using so much power?");
  }
  const top = parked[0];
  if (top?.device_ids[0]) out.push(`Go back to the ${name(top.device_ids[0])}`);
  for (const d of devices) {
    if (d.attributes.state === "RUNNING" && d.info.kind !== "other") out.push(`How long until the ${said(d)} finishes?`);
    if (d.info.kind === "other") out.push(`What is the status of the ${said(d)}?`);
  }
  const dryer = devices.find((d) => d.info.kind === "dryer");
  const ac = devices.find((d) => d.info.kind === "ac");
  if (dryer) out.push(`Is the ${said(dryer)} done?`);
  if (ac) out.push(`Set the ${said(ac)} to 24 degrees`);
  return [...new Set(out)].slice(0, MAX);
}
