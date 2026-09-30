import { ArrowLeft, Eye, EyeOff, LoaderCircle } from "lucide-react";
import { useId, useState, type InputHTMLAttributes, type ReactNode } from "react";
import { Link } from "react-router";
import { Backdrop } from "../../components/glass/Backdrop";
import { Logo } from "../../components/glass/Logo";

/** Only in-app destinations: a crafted ?next= can't send someone off to another site after they sign in. */
export function safeNext(next: string | null): string {
  return next && next.startsWith("/app") && !next.startsWith("//") && !next.includes("\\") ? next : "/app";
}

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children: ReactNode }) {
  return (
    <>
      <Backdrop />
      <div className="flex min-h-dvh flex-col items-center justify-center px-4 py-10">
        <div className="mb-6 flex w-full max-w-[440px] items-center justify-between">
          <Logo />
          <Link to="/" className="inline-flex items-center gap-1.5 t-caption text-ink-80 hover:text-ink">
            <ArrowLeft size={15} aria-hidden="true" /> Home
          </Link>
        </div>
        <main className="glass window-enter w-full max-w-[440px] rounded-xl p-7 sm:p-9">
          <h1 className="t-display">{title}</h1>
          {subtitle && <p className="t-caption mt-2 text-ink-80">{subtitle}</p>}
          <div className="mt-7">{children}</div>
        </main>
      </div>
    </>
  );
}

type FieldProps = InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string | null; hint?: string };

export function Field({ label, error, hint, ...input }: FieldProps) {
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div>
      <label htmlFor={id} className="t-caption-strong">
        {label}
      </label>
      <input id={id} className="field mt-1.5" aria-invalid={error ? true : undefined} aria-describedby={describedBy} {...input} />
      {error ? (
        <p id={`${id}-error`} className="t-fine mt-1.5 text-bad-text">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="t-fine mt-1.5 text-ink-48">
            {hint}
          </p>
        )
      )}
    </div>
  );
}

export function PasswordField(props: Omit<FieldProps, "type">) {
  const [shown, setShown] = useState(false);
  return (
    <div className="relative">
      <Field {...props} type={shown ? "text" : "password"} />
      <button
        type="button"
        onClick={() => setShown((s) => !s)}
        className="pressable absolute right-2 top-[34px] grid h-9 w-9 place-items-center rounded-full text-ink-48 hover:text-ink"
        aria-label={shown ? "Hide password" : "Show password"}
      >
        {shown ? <EyeOff size={17} aria-hidden="true" /> : <Eye size={17} aria-hidden="true" />}
      </button>
    </div>
  );
}

export function SubmitButton({ pending, children }: { pending: boolean; children: ReactNode }) {
  return (
    <button type="submit" className="btn-pill mt-2 w-full" disabled={pending}>
      {pending && <LoaderCircle size={17} className="animate-spin" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-md bg-bad/10 px-4 py-3 t-caption text-bad-text">
      {message}
    </p>
  );
}

export function AccountsOff() {
  return (
    <div className="space-y-4">
      <p className="t-caption text-ink-80">Accounts aren't switched on for this server yet. You can still try everything on the demo home.</p>
      <Link to="/demo" className="btn-pill w-full">
        Try the live demo
      </Link>
    </div>
  );
}
