import { LoaderCircle } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { changePassword, friendlyError, MIN_PASSWORD, sendPasswordReset, validateEmail, validatePassword } from "../../lib/account";
import { useAuth } from "../../lib/auth";
import { AuthLayout, Field, FormError, PasswordField, SubmitButton } from "./AuthLayout";

/** /forgot: ask for a reset link. Says the same thing whether or not the account exists. */
export function Forgot() {
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const problem = validateEmail(email);
    setEmailError(problem);
    if (problem) return;
    setPending(true);
    setError(null);
    try {
      await sendPasswordReset(email);
      setSent(true);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthLayout title="Reset your password" subtitle={sent ? undefined : "We'll email you a link to choose a new one."}>
      {sent ? (
        <div className="space-y-5">
          <p className="t-body text-ink-80">If there's an account for {email.trim()}, a reset link is on its way.</p>
          <Link to="/login" className="btn-pill-ghost w-full">
            Back to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <FormError message={error} />
          <Field label="Email" type="email" autoComplete="email" inputMode="email" value={email}
                 onChange={(e) => setEmail(e.target.value)} error={emailError} required />
          <SubmitButton pending={pending}>Send reset link</SubmitButton>
        </form>
      )}
    </AuthLayout>
  );
}

const LINK_GRACE_MS = 4000; // the link's code is exchanged in the background right after the page loads

/** /reset: the reset link signs the person in for a moment, just long enough to set a new password. */
export function Reset() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<{ password?: string | null; confirm?: string | null }>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setGaveUp(true), LINK_GRACE_MS);
    return () => clearTimeout(timer);
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = { password: validatePassword(password), confirm: password === confirm ? null : "The passwords don't match." };
    setErrors(found);
    if (found.password || found.confirm) return;
    setPending(true);
    setError(null);
    try {
      await changePassword(password);
      navigate("/app", { replace: true });
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setPending(false);
    }
  }

  if (auth.status === "off") return <Navigate to="/demo" replace />;
  if (auth.status !== "signed_in") {
    return (
      <AuthLayout title="Choose a new password">
        {gaveUp ? (
          <div className="space-y-5">
            <p className="t-body text-ink-80">This reset link has expired or was already used.</p>
            <Link to="/forgot" className="btn-pill w-full">
              Send a new link
            </Link>
          </div>
        ) : (
          <p className="flex items-center gap-2 t-caption text-ink-80">
            <LoaderCircle size={16} className="animate-spin" aria-hidden="true" /> Checking your link…
          </p>
        )}
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Choose a new password" subtitle={`At least ${MIN_PASSWORD} characters.`}>
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <FormError message={error} />
        <PasswordField label="New password" autoComplete="new-password" value={password}
                       onChange={(e) => setPassword(e.target.value)} error={errors.password} required />
        <PasswordField label="Repeat it" autoComplete="new-password" value={confirm}
                       onChange={(e) => setConfirm(e.target.value)} error={errors.confirm} required />
        <SubmitButton pending={pending}>Save password</SubmitButton>
      </form>
    </AuthLayout>
  );
}

/** /confirm: where the sign-up email lands. On the same device it signs you in; elsewhere, you sign in once. */
export function Confirm() {
  const auth = useAuth();
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setGaveUp(true), LINK_GRACE_MS);
    return () => clearTimeout(timer);
  }, []);

  if (auth.status === "signed_in") return <Navigate to="/app" replace />;
  return (
    <AuthLayout title={gaveUp ? "Email confirmed" : "Confirming your email"}>
      {gaveUp ? (
        <div className="space-y-5">
          <p className="t-body text-ink-80">You're all set. Sign in to open your home.</p>
          <Link to="/login" className="btn-pill w-full">
            Sign in
          </Link>
        </div>
      ) : (
        <p className="flex items-center gap-2 t-caption text-ink-80">
          <LoaderCircle size={16} className="animate-spin" aria-hidden="true" /> One moment…
        </p>
      )}
    </AuthLayout>
  );
}
