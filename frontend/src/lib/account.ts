import { create } from "zustand";
import { requireSupabase } from "./supabase";
import { socket } from "./ws";

export const MIN_PASSWORD = 8;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type Profile = { display_name: string; home_name: string; onboarded: boolean; created_at: string };
type ProfilePatch = Partial<Pick<Profile, "display_name" | "home_name" | "onboarded">>;

/** Turns Supabase's messages into sentences people can act on. Unknown ones pass through. */
export function friendlyError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error ?? "");
  const known: [RegExp, string][] = [
    [/invalid login credentials/i, "That email and password don't match. Check both and try again."],
    [/email not confirmed/i, "Confirm your email first. The link is in your inbox."],
    [/already registered|already been registered/i, "There's already an account with that email. Sign in instead."],
    [/rate limit|too many/i, "Too many attempts. Wait a minute, then try again."],
    [/password should be|weak password/i, `Use a stronger password: at least ${MIN_PASSWORD} characters.`],
    [/same password|different from the old/i, "Pick a password you haven't used here before."],
    [/failed to fetch|network/i, "We couldn't reach the server. Check your connection."],
  ];
  return known.find(([pattern]) => pattern.test(message))?.[1] ?? (message || "Something went wrong. Try again.");
}

export function validateEmail(email: string): string | null {
  return EMAIL.test(email.trim()) ? null : "Enter a valid email address.";
}

export function validatePassword(password: string): string | null {
  return password.length >= MIN_PASSWORD ? null : `Use at least ${MIN_PASSWORD} characters.`;
}

export async function signIn(email: string, password: string): Promise<void> {
  const supabase = await requireSupabase();
  const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
  if (error) throw error;
}

/** Returns true when the account is ready now, false when the email must be confirmed first. */
export async function signUp(email: string, password: string, displayName: string): Promise<boolean> {
  const supabase = await requireSupabase();
  const { data, error } = await supabase.auth.signUp({
    email: email.trim(),
    password,
    options: { emailRedirectTo: `${location.origin}/confirm`, data: { display_name: displayName.trim().slice(0, 60) } },
  });
  if (error) throw error;
  return data.session !== null;
}

export async function sendPasswordReset(email: string): Promise<void> {
  const supabase = await requireSupabase();
  const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), { redirectTo: `${location.origin}/reset` });
  if (error) throw error;
}

export async function changePassword(password: string): Promise<void> {
  const supabase = await requireSupabase();
  const { error } = await supabase.auth.updateUser({ password });
  if (error) throw error;
  await supabase.auth.signOut({ scope: "others" }); // a changed password should lock out any other device
}

export async function signOut(everywhere = false): Promise<void> {
  socket.stop();
  const supabase = await requireSupabase();
  await supabase.auth.signOut({ scope: everywhere ? "global" : "local" });
  useProfile.getState().clear();
}

export async function deleteAccount(): Promise<void> {
  const supabase = await requireSupabase();
  const { error } = await supabase.rpc("delete_my_account");
  if (error) throw error;
  socket.stop();
  await supabase.auth.signOut({ scope: "local" });
  useProfile.getState().clear();
}

type ProfileState = {
  profile: Profile | null;
  status: "idle" | "loading" | "ready" | "error";
  load: (userId: string) => Promise<void>;
  save: (userId: string, patch: ProfilePatch) => Promise<void>;
  clear: () => void;
};

export const useProfile = create<ProfileState>()((set, get) => ({
  profile: null,
  status: "idle",
  load: async (userId) => {
    if (get().status === "loading") return;
    set({ status: "loading" });
    try {
      const supabase = await requireSupabase();
      const { data, error } = await supabase
        .from("profiles")
        .select("display_name,home_name,onboarded,created_at")
        .eq("id", userId)
        .maybeSingle();
      if (error) throw error;
      set({ profile: data as Profile | null, status: "ready" });
    } catch {
      set({ status: "error" });
    }
  },
  save: async (userId, patch) => {
    const supabase = await requireSupabase();
    const { error } = await supabase.from("profiles").update(patch).eq("id", userId);
    if (error) throw error;
    const current = get().profile;
    if (current) set({ profile: { ...current, ...patch } });
  },
  clear: () => set({ profile: null, status: "idle" }),
}));
