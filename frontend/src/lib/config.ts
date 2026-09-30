import { apiHeaders, apiUrl } from "./backend";

/** What the server says this deployment supports. Read once; the same build works on any deployment. */
export type SiteConfig = {
  accounts: boolean;
  supabase_url: string | null;
  supabase_publishable_key: string | null;
  smartthings: boolean;
  llm: string;
};

let pending: Promise<SiteConfig> | null = null;

export function loadConfig(): Promise<SiteConfig> {
  pending ??= fetch(apiUrl("/api/config"), { headers: apiHeaders })
    .then((response) => {
      if (!response.ok) throw new Error(`config request failed (${response.status})`);
      return response.json() as Promise<SiteConfig>;
    })
    .catch((error: unknown) => {
      pending = null; // let the next caller retry
      throw error;
    });
  return pending;
}
