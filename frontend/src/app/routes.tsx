import { LoaderCircle } from "lucide-react";
import { lazy, Suspense, useEffect, type ReactNode } from "react";
import { createBrowserRouter, Link, Navigate, Outlet, useLocation } from "react-router";
import { Backdrop } from "../components/glass/Backdrop";
import { AuthProvider, useAuth } from "../lib/auth";
import Landing from "../pages/landing/Landing";

const AppShell = lazy(() => import("../pages/app/AppShell"));
const HomePage = lazy(() => import("../pages/app/home/HomePage"));
const AssistantPage = lazy(() => import("../pages/app/AssistantPage"));
const IntegrationsPage = lazy(() => import("../pages/app/IntegrationsPage"));
const ProfilePage = lazy(() => import("../pages/app/ProfilePage"));
const SignIn = lazy(() => import("../pages/auth/SignIn"));
const SignUp = lazy(() => import("../pages/auth/SignUp"));
const Forgot = lazy(() => import("../pages/auth/Recover").then((m) => ({ default: m.Forgot })));
const Reset = lazy(() => import("../pages/auth/Recover").then((m) => ({ default: m.Reset })));
const Confirm = lazy(() => import("../pages/auth/Recover").then((m) => ({ default: m.Confirm })));

function Splash() {
  return (
    <>
      <Backdrop />
      <p className="flex min-h-dvh items-center justify-center gap-2 t-caption text-ink-80" role="status">
        <LoaderCircle size={17} className="animate-spin" aria-hidden="true" /> Loading…
      </p>
    </>
  );
}

function Page({ children }: { children: ReactNode }) {
  return <Suspense fallback={<Splash />}>{children}</Suspense>;
}

/** Accounts load only where they're needed, so the landing page never downloads the auth client. */
function WithAccounts() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const location = useLocation();
  if (auth.status === "loading") return <Splash />;
  if (auth.status === "off") return <Navigate to="/demo" replace />;
  if (auth.status === "error") return <Trouble title="Can't reach the server" message="Check your connection, then reload." />;
  if (auth.status === "signed_out") {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  }
  return <>{children}</>;
}

function Titled({ title, children }: { title: string; children: ReactNode }) {
  useEffect(() => {
    document.title = title;
  }, [title]);
  return <>{children}</>;
}

function FullPageNote({ eyebrow, title, message, children }: { eyebrow: string; title: string; message: string; children: ReactNode }) {
  return (
    <Titled title={`${title} · PROCASTO`}>
      <Backdrop />
      <main className="flex min-h-dvh items-center justify-center px-4">
        <div className="glass w-full max-w-[440px] rounded-xl p-8 text-center">
          <p className="t-eyebrow text-ink-48">{eyebrow}</p>
          <h1 className="t-display mt-2">{title}</h1>
          <p className="t-caption mt-2 text-ink-80">{message}</p>
          <div className="mt-6 flex justify-center gap-2">{children}</div>
        </div>
      </main>
    </Titled>
  );
}

function NotFound() {
  return (
    <FullPageNote eyebrow="404" title="Nothing here" message="That page doesn't exist, or it moved.">
      <Link to="/" className="btn-pill">Home</Link>
      <Link to="/demo" className="btn-pill-ghost">Try the demo</Link>
    </FullPageNote>
  );
}

/** Also catches a page that fails to download, e.g. an old tab after the site was updated. */
function Trouble({ title = "Something went wrong", message = "This page didn't load. Reloading usually fixes it." }) {
  return (
    <FullPageNote eyebrow="Sorry" title={title} message={message}>
      <button type="button" className="btn-pill" onClick={() => window.location.reload()}>Reload</button>
      <a href="/" className="btn-pill-ghost">Home</a>
    </FullPageNote>
  );
}

const appPages = [
  { index: true, element: <Page><HomePage /></Page>, handle: { title: "Home" } },
  { path: "assistant", element: <Page><AssistantPage /></Page>, handle: { title: "Assistant" } },
];

export const router = createBrowserRouter([{ errorElement: <Trouble />, children: [
  { path: "/", element: <Titled title="PROCASTO · Your home, explained"><Landing /></Titled> },
  {
    path: "/demo",
    element: <Titled title="Demo · PROCASTO"><Page><AppShell mode="demo" /></Page></Titled>,
    children: appPages,
  },
  {
    element: <WithAccounts />,
    children: [
      { path: "/login", element: <Titled title="Sign in · PROCASTO"><Page><SignIn /></Page></Titled> },
      { path: "/signup", element: <Titled title="Create account · PROCASTO"><Page><SignUp /></Page></Titled> },
      { path: "/forgot", element: <Titled title="Reset password · PROCASTO"><Page><Forgot /></Page></Titled> },
      { path: "/reset", element: <Titled title="New password · PROCASTO"><Page><Reset /></Page></Titled> },
      { path: "/confirm", element: <Titled title="Confirming · PROCASTO"><Page><Confirm /></Page></Titled> },
      {
        path: "/app",
        element: (
          <Titled title="PROCASTO">
            <RequireAuth>
              <Page><AppShell mode="account" /></Page>
            </RequireAuth>
          </Titled>
        ),
        children: [
          ...appPages,
          { path: "integrations", element: <Page><IntegrationsPage /></Page>, handle: { title: "Devices" } },
          { path: "profile", element: <Page><ProfilePage /></Page>, handle: { title: "Profile" } },
        ],
      },
    ],
  },
  { path: "*", element: <NotFound /> },
] }]);
