import { create } from "zustand";
import { useShell } from "../pages/app/shell";
import { useAuth } from "./auth";
import { useStore } from "./store";
import { requireSupabase } from "./supabase";

/**
 * Choices the account doesn't hold yet: a save still in flight, or a demo visit (which has no account).
 * `basis` names what they were made against, so a newer saved list, or a different user, wins on its own.
 */
const useChoices = create<{ basis: string | null; ids: string[] }>(() => ({ basis: null, ids: [] }));

/** Devices you follow for in-app updates: all of them until you choose. Signed in, the choice follows your account. */
export function useWatchlist(deviceIds: string[]) {
  const { mode } = useShell();
  const auth = useAuth();
  const user = mode === "account" && auth.status === "signed_in" ? auth.session.user : null;
  const raw: unknown = user?.user_metadata?.procasto_watch_ids;
  const saved = Array.isArray(raw) ? raw.filter((id): id is string => typeof id === "string") : null;
  const basis = `${user?.id ?? "demo"}:${JSON.stringify(saved)}`;
  const choices = useChoices();
  const chosen = choices.basis === basis ? choices.ids : saved;
  const watched = new Set(chosen ?? deviceIds);

  async function toggleMany(ids: string[], on: boolean) {
    const next = new Set(chosen ?? deviceIds);
    for (const id of ids) {
      if (on) next.add(id);
      else next.delete(id);
    }
    const value = [...next];
    useChoices.setState({ basis, ids: value });
    if (!user) return;
    try {
      const supabase = await requireSupabase();
      const { error } = await supabase.auth.updateUser({ data: { procasto_watch_ids: value } });
      if (error) throw error;
    } catch {
      useChoices.setState({ basis: null, ids: [] }); // back to what's saved
      useStore.getState().showToast("Could not save your update choices. Try again.");
    }
  }

  return { watched, toggleMany };
}
