export function formatPower(watts: number | null | undefined): string {
  if (watts == null) return "–";
  return watts >= 1000 ? `${(watts / 1000).toFixed(1)} kW` : `${Math.round(watts)} W`;
}

export function formatTemp(celsius: number | null | undefined): string {
  return celsius == null ? "–" : `${Number(celsius.toFixed(1))} °C`;
}

export function formatSeconds(ms: number): string {
  const abs = Math.abs(ms);
  return abs >= 1000 ? `${(abs / 1000).toFixed(1)} s` : `${Math.round(abs)} ms`;
}

export function timeAgo(iso: string | null | undefined, now: number): string {
  if (!iso) return "";
  const seconds = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (seconds < 2) return "just now";
  if (seconds < 60) return `${seconds} s ago`;
  return `${Math.round(seconds / 60)} min ago`;
}
