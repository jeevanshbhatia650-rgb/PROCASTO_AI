import { spokenName } from "../../../lib/deviceView";
import type { DeviceSnapshot } from "../../../types/generated";

/** The most useful question to ask about one device right now, phrased the way the assistant understands. */
export function questionFor(device: DeviceSnapshot): string {
  const name = spokenName(device.info.display_name);
  const a = device.attributes;
  if (a.error_code) return `What does ${a.error_code} mean on the ${name}?`;
  if (device.info.kind === "ac") return "Why is the AC using so much power?";
  if (device.info.kind === "other") return `What is the status of the ${name}?`;
  if (a.state === "RUNNING") return `How long until the ${name} finishes?`;
  return `Is the ${name} done?`;
}

export function askLink(base: string, question: string): string {
  return `${base}/assistant?ask=${encodeURIComponent(question)}`;
}
