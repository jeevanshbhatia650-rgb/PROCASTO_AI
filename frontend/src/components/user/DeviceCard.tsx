import type { DeviceSnapshot } from "../../types/generated";
import { formatPower, formatTemp } from "../../lib/format";
import { DeviceIcon } from "../icons";

const SPIKE_W = 2500;
const METER_MAX_W = 3500;

type View = { value: string; status: string; tone: "ok" | "run" | "bad" | "off" | "warn" };

function view(snapshot: DeviceSnapshot): View {
  const a = snapshot.attributes as Record<string, number | string | null | undefined>;
  const power = a.power_w as number | undefined;
  if (a.error_code) return { value: "Stopped", status: `Error ${a.error_code} · ${formatPower(power)}`, tone: "bad" };
  if (snapshot.info.kind === "ac") {
    if (a.state === "OFF") return { value: "Off", status: `Room ${formatTemp(a.temp_c as number)}`, tone: "off" };
    const spike = power !== undefined && power > SPIKE_W;
    return {
      value: formatPower(power),
      status: `Cooling to ${formatTemp(a.target_temp_c as number)} · room ${formatTemp(a.temp_c as number)}`,
      tone: spike ? "warn" : "ok",
    };
  }
  if (a.state === "RUNNING") {
    const water = a.temp_c != null ? ` · ${formatTemp(a.temp_c as number)}` : "";
    return { value: `${a.remaining_min} min`, status: `Running · ${formatPower(power)}${water}`, tone: "run" };
  }
  if (a.state === "DONE") return { value: "Done", status: "Cycle finished", tone: "ok" };
  return { value: a.state === "IDLE" ? "Idle" : String(a.state ?? "…"), status: `Standby · ${formatPower(power)}`, tone: "off" };
}

const DOT: Record<View["tone"], string> = {
  ok: "bg-ok",
  run: "bg-ok",
  warn: "bg-run",
  bad: "bg-bad-dark",
  off: "bg-off",
};

export function DeviceCard({ snapshot }: { snapshot: DeviceSnapshot }) {
  const v = view(snapshot);
  const dark = v.tone === "bad";
  const power = Number(snapshot.attributes.power_w ?? 0);
  return (
    <article
      key={dark ? "fault" : "ok"}
      className={`rounded-lg p-4 transition-[background-color,color,border-color] duration-300 ${
        dark ? "changed-ring border border-transparent bg-tile-1 text-white" : "border border-hairline bg-canvas text-ink"
      }`}
      aria-label={`${snapshot.info.display_name}: ${v.value}, ${v.status}`}
    >
      <div className={`flex items-center gap-2 t-caption ${dark ? "text-body-muted" : "text-ink-48"}`}>
        <DeviceIcon kind={snapshot.info.kind} size={17} />
        <span className={`t-caption-strong ${dark ? "text-white" : "text-ink"}`}>{snapshot.info.display_name}</span>
        <span className="ml-auto t-fine">{snapshot.info.model_id}</span>
      </div>
      <p className="t-section tabular mt-3">{v.value}</p>
      <p className={`mt-1 flex items-center gap-1.5 t-caption ${dark ? "text-bad-dark" : "text-ink-80"}`}>
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${DOT[v.tone]}`} />
        <span className="truncate">{v.status}</span>
      </p>
      <div className={`mt-3 h-1 overflow-hidden rounded-full ${dark ? "bg-white/10" : "bg-divider"}`} aria-hidden="true">
        <div
          className={`h-full origin-left rounded-full transition-transform duration-500 ease-out ${v.tone === "warn" ? "bg-run" : dark ? "bg-bad-dark" : "bg-primary/70"}`}
          style={{ transform: `scaleX(${Math.min(1, power / METER_MAX_W)})` }}
        />
      </div>
    </article>
  );
}
