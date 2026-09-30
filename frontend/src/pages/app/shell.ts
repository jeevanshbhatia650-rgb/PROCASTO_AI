import { createContext, useContext, useEffect, useState } from "react";
import { loadConfig, type SiteConfig } from "../../lib/config";

export type ShellMode = "demo" | "account";

/** Which kind of visit this is: a signed-out demo (/demo) or a signed-in account (/app). */
export const ShellContext = createContext<{ mode: ShellMode; base: "/demo" | "/app" }>({ mode: "demo", base: "/demo" });

export function useShell() {
  return useContext(ShellContext);
}

export function useSiteConfig(): SiteConfig | null {
  const [config, setConfig] = useState<SiteConfig | null>(null);
  useEffect(() => {
    let alive = true;
    loadConfig()
      .then((value) => alive && setConfig(value))
      .catch(() => {}); // pages fall back to what the socket tells them
    return () => {
      alive = false;
    };
  }, []);
  return config;
}

export function initials(name: string, email: string): string {
  const source = name.trim() || email.split("@")[0] || "?";
  const parts = source.split(/[\s._-]+/).filter(Boolean);
  const letters = parts.length > 1 ? `${parts[0]?.[0] ?? ""}${parts[1]?.[0] ?? ""}` : source.slice(0, 2);
  return letters.toUpperCase();
}
