import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { friendlyError, signIn, validateEmail } from "../../lib/account";
import { useAuth } from "../../lib/auth";
import { AccountsOff, AuthLayout, Field, FormError, PasswordField, safeNext, SubmitButton } from "./AuthLayout";

export default function SignIn() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (auth.status === "signed_in") return <Navigate to={next} replace />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const problem = validateEmail(email);
    setEmailError(problem);
    if (problem || !password) return setError(problem ? null : "Enter your password.");
    setPending(true);
    setError(null);
    try {
      await signIn(email, password);
      navigate(next, { replace: true });
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to see your home and ask about it.">
      {auth.status === "off" ? (
        <AccountsOff />
      ) : (
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <FormError message={error ?? (auth.status === "error" ? "We couldn't reach the server. Try again in a moment." : null)} />
          <Field label="Email" type="email" autoComplete="email" inputMode="email" value={email}
                 onChange={(e) => setEmail(e.target.value)} error={emailError} required />
          <PasswordField label="Password" autoComplete="current-password" value={password}
                         onChange={(e) => setPassword(e.target.value)} required />
          <div className="flex justify-end">
            <Link to="/forgot" className="t-caption text-ink-80 underline-offset-4 hover:underline">
              Forgot password?
            </Link>
          </div>
          <SubmitButton pending={pending}>Sign in</SubmitButton>
          <p className="t-caption pt-2 text-center text-ink-80">
            New here?{" "}
            <Link to="/signup" className="t-caption-strong text-ink underline-offset-4 hover:underline">
              Create an account
            </Link>{" "}
            or{" "}
            <Link to="/demo" className="t-caption-strong text-ink underline-offset-4 hover:underline">
              try the demo
            </Link>
            .
          </p>
        </form>
      )}
    </AuthLayout>
  );
}
