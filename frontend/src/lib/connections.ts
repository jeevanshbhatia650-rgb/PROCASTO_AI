import { apiHeaders, apiUrl } from "./backend";
import { freshToken, requireSupabase } from "./supabase";

const SMARTTHINGS_LOGIN = "https://api.smartthings.com/oauth/authorize?";
const OAUTH_ROUND_TRIP_S = 900; // enough token lifetime to finish the Samsung login

export type Connection = { provider: "smartthings"; status: string; account_label: string; connected_at: string };

export async function listConnections(): Promise<Connection[]> {
  const supabase = await requireSupabase();
  const { data, error } = await supabase.from("connections").select("provider,status,account_label,connected_at");
  if (error) throw error;
  return (data ?? []) as Connection[];
}

async function authorized(path: string, method: "POST" | "DELETE"): Promise<Response> {
  const token = await freshToken(OAUTH_ROUND_TRIP_S);
  if (!token) throw new Error("Your session expired. Sign in again.");
  const response = await fetch(apiUrl(path), { method, headers: { ...apiHeaders, Authorization: `Bearer ${token}` } });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Request failed (${response.status}).`);
  }
  return response;
}

/** Sends the browser to Samsung to approve access. It comes back to /app/integrations. */
export async function connectSmartThings(): Promise<void> {
  const response = await authorized("/api/connections/smartthings/start", "POST");
  const { authorize_url } = (await response.json()) as { authorize_url: string };
  if (!authorize_url.startsWith(SMARTTHINGS_LOGIN)) throw new Error("Unexpected login address. Nothing was opened.");
  window.location.assign(authorize_url);
}

export async function disconnectSmartThings(): Promise<void> {
  await authorized("/api/connections/smartthings", "DELETE");
}

/** What the `?smartthings=` flag on /app/integrations means, after the Samsung login. */
const SMARTTHINGS_RESULT: Record<string, { ok: boolean; message: string }> = {
  connected: { ok: true, message: "SmartThings is connected. Your devices are loading." },
  failed: { ok: false, message: "Samsung didn't respond, so nothing was connected. Try again in a minute." },
  denied: { ok: false, message: "No changes: access wasn't approved at Samsung." },
  expired: { ok: false, message: "That login took too long or was already used. Start again." },
  save_failed: { ok: false, message: "Samsung approved, but we couldn't save the connection. Try again." },
  off: { ok: false, message: "SmartThings isn't set up on this server yet." },
};

export function smartthingsResult(flag: string | null): { ok: boolean; message: string } | null {
  return flag && Object.hasOwn(SMARTTHINGS_RESULT, flag) ? SMARTTHINGS_RESULT[flag]! : null;
}
