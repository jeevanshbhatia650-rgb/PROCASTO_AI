import { MailCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { friendlyError, MIN_PASSWORD, signUp, validateEmail, validatePassword } from "../../lib/account";
import { useAuth } from "../../lib/auth";
import { AccountsOff, AuthLayout, Field, FormError, PasswordField, SubmitButton } from "./AuthLayout";

export default function SignUp() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ email?: string | null; password?: string | null }>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);

  if (auth.status === "signed_in" && !sentTo) return <Navigate to="/app" replace />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = { email: validateEmail(email), password: validatePassword(password) };
    setErrors(found);
    if (found.email || found.password) return;
    setPending(true);
    setError(null);
    try {
      const ready = await signUp(email, password, name);
      if (ready) navigate("/app", { replace: true });
      else setSentTo(email.trim());
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setPending(false);
    }
  }

  if (sentTo) {
    return (
      <AuthLayout title="Check your inbox">
        <div className="space-y-5">
          <span className="grid h-12 w-12 place-items-center rounded-full bg-ink text-white">
            <MailCheck size={22} aria-hidden="true" />
          </span>
          <p className="t-body text-ink-80">
            We sent a confirmation link to <strong className="text-ink">{sentTo}</strong>. Open it on this device to finish
            and go straight to your home.
          </p>
          <p className="t-caption text-ink-48">Nothing there? Check spam, or wait a minute: the first email can be slow.</p>
          <button type="button" className="btn-pill-ghost w-full" onClick={() => setSentTo(null)}>
            Use a different email
          </button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Create your account" subtitle="Then connect SmartThings, or keep exploring the demo home.">
      {auth.status === "off" ? (
        <AccountsOff />
      ) : (
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <FormError message={error} />
          <Field label="Your name" hint="Optional. Used to greet you." autoComplete="name" value={name} maxLength={60}
                 onChange={(e) => setName(e.target.value)} />
          <Field label="Email" type="email" autoComplete="email" inputMode="email" value={email}
                 onChange={(e) => setEmail(e.target.value)} error={errors.email} required />
          <PasswordField label="Password" autoComplete="new-password" value={password} hint={`At least ${MIN_PASSWORD} characters.`}
                         onChange={(e) => setPassword(e.target.value)} error={errors.password} required />
          <SubmitButton pending={pending}>Create account</SubmitButton>
          <p className="t-caption pt-2 text-center text-ink-80">
            Already have one?{" "}
            <Link to="/login" className="t-caption-strong text-ink underline-offset-4 hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      )}
    </AuthLayout>
  );
}
