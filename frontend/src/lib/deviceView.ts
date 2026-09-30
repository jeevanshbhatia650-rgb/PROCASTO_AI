import type { DeviceSnapshot } from "../types/generated";
import { formatPower, formatTemp } from "./format";

export const SPIKE_W = 2500;

export type Tone = "ok" | "run" | "bad" | "off" | "warn";

/** A device name mid-sentence: "the washer", but "the AC" and "the living room TV" keep their capitals. */
export function spokenName(name: string): string {
  return name
    .split(" ")
    .map((word) => (word.length > 1 && word === word.toUpperCase() ? word : word.toLowerCase()))
    .join(" ");
}
export type DeviceView = { value: string; status: string; tone: Tone };

/** One device, in words: the big value, the line under it, and the state it's in. */
export function deviceView(snapshot: DeviceSnapshot): DeviceView {
  const a = snapshot.attributes as Record<string, number | string | null | undefined>;
  const power = a.power_w as number | undefined;
  if (a.error_code) return { value: "Stopped", status: `Error ${a.error_code} · ${formatPower(power)}`, tone: "bad" };
  if (snapshot.info.kind === "other") {
    if (!a.state) return { value: "Connected", status: "No live state yet", tone: "ok" };
    const on = a.state !== "OFF";
    return { value: on ? "On" : "Off", status: power == null ? "Live status" : formatPower(power), tone: on ? "ok" : "off" };
  }
  if (snapshot.info.kind === "ac") {
    if (a.state === "OFF") return { value: "Off", status: `Room ${formatTemp(a.temp_c as number)}`, tone: "off" };
    return {
      value: formatPower(power),
      status: `Cooling to ${formatTemp(a.target_temp_c as number)} · room ${formatTemp(a.temp_c as number)}`,
      tone: power !== undefined && power > SPIKE_W ? "warn" : "ok",
    };
  }
  if (a.state === "RUNNING") {
    const water = a.temp_c != null ? ` · ${formatTemp(a.temp_c as number)}` : "";
    return { value: a.remaining_min == null ? "Running" : `${a.remaining_min} min`, status: `Running · ${formatPower(power)}${water}`, tone: "run" };
  }
  if (a.state === "DONE") return { value: "Done", status: "Cycle finished", tone: "ok" };
  return { value: a.state === "IDLE" ? "Idle" : String(a.state ?? "…"), status: `Standby · ${formatPower(power)}`, tone: "off" };
}

/** Devices that need a person: a fault, or an AC drawing far more than it should. */
export function needsAttention(snapshot: DeviceSnapshot): boolean {
  const tone = deviceView(snapshot).tone;
  return tone === "bad" || tone === "warn";
}

/** The part of a device worth a notification when it changes: its state, a fault, a spike. Never a new reading. */
export function alertKey(snapshot: DeviceSnapshot): string {
  const a = snapshot.attributes;
  return `${String(a.state ?? "")}|${String(a.error_code ?? "")}|${needsAttention(snapshot)}`;
}

export function alertText(snapshot: DeviceSnapshot): string {
  const a = snapshot.attributes;
  const name = snapshot.info.display_name;
  if (a.error_code) return `${name} stopped · error ${String(a.error_code)}`;
  if (needsAttention(snapshot)) return `${name} is drawing unusually high power`;
  if (a.state === "DONE") return `${name} finished`;
  return `${name} is ${String(a.state ?? "updated").toLowerCase()}`;
}
