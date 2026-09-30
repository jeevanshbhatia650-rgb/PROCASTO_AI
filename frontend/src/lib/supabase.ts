import type { SupabaseClient } from "@supabase/supabase-js";
import { loadConfig } from "./config";

let client: Promise<SupabaseClient | null> | null = null;

/**
 * The Supabase client, or null when this deployment runs without accounts.
 * Loaded on first use, so the landing page never downloads it.
 */
export function getSupabase(): Promise<SupabaseClient | null> {
  client ??= loadConfig().then(async (config) => {
    if (!config.accounts || !config.supabase_url || !config.supabase_publishable_key) return null;
    const { createClient } = await import("@supabase/supabase-js");
    return createClient(config.supabase_url, config.supabase_publishable_key, {
      auth: { flowType: "pkce", persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    });
  });
  client.catch(() => {
    client = null; // a failed config fetch shouldn't stick
  });
  return client;
}

export async function requireSupabase(): Promise<SupabaseClient> {
  const supabase = await getSupabase();
  if (!supabase) throw new Error("Accounts are turned off on this server.");
  return supabase;
}

/** A current access token, refreshed first when it has less than `minValidS` left. */
export async function freshToken(minValidS = 60): Promise<string | null> {
  const supabase = await getSupabase();
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  const session = data.session;
  if (!session) return null;
  const secondsLeft = (session.expires_at ?? 0) - Date.now() / 1000;
  if (secondsLeft > minValidS) return session.access_token;
  const refreshed = await supabase.auth.refreshSession();
  if (refreshed.error) throw refreshed.error;
  return refreshed.data.session?.access_token ?? null;
}
