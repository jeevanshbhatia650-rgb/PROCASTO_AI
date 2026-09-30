import { LoaderCircle, LogOut, ShieldCheck, Trash } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { changePassword, deleteAccount, friendlyError, signOut, useProfile, validatePassword } from "../../lib/account";
import { useAuth } from "../../lib/auth";
import { Field, PasswordField } from "../auth/AuthLayout";
import { initials } from "./shell";

const DELETE_WORD = "DELETE";

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="card p-6 sm:p-7" aria-label={title}>
      <h2 className="t-tagline">{title}</h2>
      {subtitle && <p className="t-caption mt-1 text-ink-80">{subtitle}</p>}
      <div className="mt-5">{children}</div>
    </section>
  );
}

function Busy({ on }: { on: boolean }) {
  return on ? <LoaderCircle size={16} className="animate-spin" aria-hidden="true" /> : null;
}

/** Mounted once the profile has loaded, so the fields start from it without syncing state in an effect. */
function DetailsForm({ userId, initial }: { userId: string; initial: { display_name: string; home_name: string } }) {
  const save = useProfile((s) => s.save);
  const [name, setName] = useState(initial.display_name);
  const [home, setHome] = useState(initial.home_name);
  const [pending, setPending] = useState(false);

  const homeError = home.trim() ? null : "Give your home a name.";
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (homeError) return;
    setPending(true);
    try {
      await save(userId, { display_name: name.trim().slice(0, 60), home_name: home.trim().slice(0, 60) });
      toast("Saved.");
    } catch (err) {
      toast.error(friendlyError(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-2">
      <Field label="Your name" value={name} maxLength={60} autoComplete="name" onChange={(e) => setName(e.target.value)} />
      <Field label="Home name" value={home} maxLength={60} error={homeError} onChange={(e) => setHome(e.target.value)} />
      <div className="sm:col-span-2">
        <button type="submit" className="btn-pill" disabled={pending}>
          <Busy on={pending} /> Save changes
        </button>
      </div>
    </form>
  );
}

function PasswordForm() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const problem = validatePassword(password);
    setError(problem);
    if (problem) return;
    setPending(true);
    try {
      await changePassword(password);
      setPassword("");
      toast("Password changed.");
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setPending(false);
    }
  };
  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-3 sm:flex-row sm:items-start">
      <div className="flex-1">
        <PasswordField label="New password" autoComplete="new-password" value={password} error={error}
                       onChange={(e) => setPassword(e.target.value)} />
      </div>
      <button type="submit" className="btn-pill sm:mt-[30px]" disabled={pending}>
        <Busy on={pending} /> Change
      </button>
    </form>
  );
}

function DangerZone() {
  const navigate = useNavigate();
  const [typed, setTyped] = useState("");
  const [pending, setPending] = useState(false);
  const [staleSignIn, setStaleSignIn] = useState(false);
  const remove = async () => {
    setPending(true);
    try {
      await deleteAccount();
      navigate("/", { replace: true });
    } catch (err) {
      // The database only deletes for a sign-in from the last few minutes, so a borrowed open tab can't.
      if (err instanceof Error && /recent sign-in required/i.test(err.message)) setStaleSignIn(true);
      else toast.error(friendlyError(err));
      setPending(false);
    }
  };
  const signInAgain = async () => {
    await signOut();
    navigate("/login?next=/app/profile", { replace: true });
  };
  return (
    <div className="space-y-4">
      <p className="t-caption text-ink-80">
        This deletes your account, your profile and any connected SmartThings login. It can't be undone.
      </p>
      <Field label={`Type ${DELETE_WORD} to confirm`} value={typed} autoComplete="off" onChange={(e) => setTyped(e.target.value)} />
      {staleSignIn ? (
        <div role="alert" className="rounded-lg bg-run/10 px-4 py-3">
          <p className="t-caption text-run-text">For your safety, sign in again, then delete your account.</p>
          <button type="button" className="btn-pill mt-3" onClick={() => void signInAgain()}>
            Sign in again
          </button>
        </div>
      ) : (
        <button type="button" className="btn-pill !bg-bad" disabled={typed !== DELETE_WORD || pending} onClick={() => void remove()}>
          <Busy on={pending} /> <Trash size={16} aria-hidden="true" /> Delete my account
        </button>
      )}
    </div>
  );
}

function DetailsUnavailable({ userId }: { userId: string }) {
  const load = useProfile((s) => s.load);
  return (
    <p className="t-caption text-ink-80">
      We couldn't load your details.{" "}
      <button type="button" className="underline underline-offset-2" onClick={() => void load(userId)}>
        Try again
      </button>
    </p>
  );
}

export default function ProfilePage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const profile = useProfile((s) => s.profile);
  const status = useProfile((s) => s.status);
  if (auth.status !== "signed_in") return null;
  const user = auth.session.user;
  const since = profile?.created_at ? new Date(profile.created_at).toLocaleDateString(undefined, { month: "long", year: "numeric" }) : "";

  const leave = async (everywhere: boolean) => {
    await signOut(everywhere);
    navigate("/", { replace: true });
  };

  return (
    <div className="grid gap-4 lg:grid-cols-12">
      <section className="tile-dark flex flex-col items-start p-6 lg:col-span-4" aria-label="Account">
        <span className="grid h-20 w-20 place-items-center rounded-full bg-white font-display text-[26px] font-semibold text-ink">
          {initials(profile?.display_name ?? "", user.email ?? "")}
        </span>
        <p className="t-display mt-5 break-all">{profile?.display_name || "Your account"}</p>
        <p className="t-caption mt-1 break-all text-white/60">{user.email}</p>
        {since && <p className="t-fine mt-4 text-white/45">Member since {since}</p>}
        <div className="mt-auto flex w-full flex-col gap-2 pt-8">
          <button type="button" className="btn-pill !bg-white !text-ink" onClick={() => void leave(false)}>
            <LogOut size={16} aria-hidden="true" /> Sign out
          </button>
          <button type="button" className="btn-pill-ghost !border-white/20 !bg-white/5 !text-white" onClick={() => void leave(true)}>
            <ShieldCheck size={16} aria-hidden="true" /> Sign out everywhere
          </button>
        </div>
      </section>
      <div className="grid gap-4 lg:col-span-8">
        <Panel title="Details" subtitle="How PROCASTO greets you and names your home.">
          {profile ? (
            <DetailsForm key={profile.created_at} userId={user.id} initial={profile} />
          ) : status === "error" || status === "ready" ? (
            <DetailsUnavailable userId={user.id} />
          ) : (
            <p className="t-caption text-ink-48">Loading…</p>
          )}
        </Panel>
        <Panel title="Password" subtitle="At least 8 characters. Your other devices get signed out.">
          <PasswordForm />
        </Panel>
        <Panel title="Delete account">
          <DangerZone />
        </Panel>
      </div>
    </div>
  );
}
