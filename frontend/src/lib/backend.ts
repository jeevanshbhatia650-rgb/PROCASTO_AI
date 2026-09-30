/**
 * Where the API and the live socket are. Empty means this same site (the backend serves the page, as in Docker).
 * When the page is hosted on its own (e.g. Vercel), the build sets VITE_BACKEND_URL to the backend's origin.
 */
const BACKEND = (import.meta.env.VITE_BACKEND_URL ?? "").replace(/\/+$/, "");

export function apiUrl(path: string): string {
  return BACKEND + path;
}

export function socketUrl(path: string): string {
  if (BACKEND) return BACKEND.replace(/^http/, "ws") + path;
  return `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${path}`;
}

/** A free ngrok tunnel answers browsers with a warning page unless asked not to. */
export const apiHeaders: Record<string, string> = /\.ngrok(-free)?\.(app|dev)$/.test(BACKEND)
  ? { "ngrok-skip-browser-warning": "1" }
  : {};
