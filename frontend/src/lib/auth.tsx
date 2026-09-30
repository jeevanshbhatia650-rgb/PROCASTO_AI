import type { Session } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getSupabase } from "./supabase";

export type AuthState =
  | { status: "loading" }
  | { status: "off" } // this deployment runs without accounts
  | { status: "error" } // the server couldn't be reached
  | { status: "signed_out" }
  | { status: "signed_in"; session: Session };

const AuthContext = createContext<AuthState>({ status: "loading" });

function fromSession(session: Session | null): AuthState {
  return session ? { status: "signed_in", session } : { status: "signed_out" };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    let alive = true;
    let unsubscribe = () => {};
    getSupabase()
      .then(async (supabase) => {
        if (!alive) return;
        if (!supabase) return setState({ status: "off" });
        const { data } = supabase.auth.onAuthStateChange((_event, session) => {
          if (alive) setState(fromSession(session)); // only set state here: Supabase warns against awaiting in this callback
        });
        unsubscribe = () => data.subscription.unsubscribe();
        const current = await supabase.auth.getSession();
        if (alive) setState(fromSession(current.data.session));
      })
      .catch(() => alive && setState({ status: "error" }));
    return () => {
      alive = false;
      unsubscribe();
    };
  }, []);

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}
