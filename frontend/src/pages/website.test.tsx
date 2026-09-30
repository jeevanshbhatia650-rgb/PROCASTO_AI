import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  state: { status: "signed_in", session: { user: { id: "user-1", email: "a@example.invalid" } } } as object,
}));

vi.mock("../lib/connections", () => ({ connectSmartThings: vi.fn(async () => {}) }));
vi.mock("../lib/config", () => ({ loadConfig: vi.fn() }));
vi.mock("../lib/account", async (original) => ({
  ...(await original<typeof import("../lib/account")>()),
  signIn: vi.fn(async () => {}),
}));
vi.mock("../lib/auth", () => ({ useAuth: () => auth.state }));

import { signIn, useProfile } from "../lib/account";
import { loadConfig } from "../lib/config";
import { connectSmartThings } from "../lib/connections";
import { ConnectWindow } from "./app/ConnectWindow";
import SignIn from "./auth/SignIn";

function stubConfig(smartthings: boolean) {
  vi.mocked(loadConfig).mockResolvedValue({
    accounts: true, supabase_url: "u", supabase_publishable_key: "k", smartthings, llm: "templates",
  });
}

beforeEach(() => {
  // jsdom has no <dialog> behaviour; this is what the browser does.
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
});

afterEach(() => {
  vi.clearAllMocks();
});

function profile(onboarded: boolean) {
  const save = vi.fn(async () => {});
  act(() =>
    useProfile.setState({
      status: "ready",
      profile: { display_name: "Neha", home_name: "Flat", onboarded, created_at: "2026-09-30T00:00:00Z" },
      save,
    }),
  );
  return save;
}

describe("the connect window (first visit)", () => {
  it("asks a new account to connect Samsung and lets them choose the demo instead", async () => {
    stubConfig(true);
    const save = profile(false);
    render(<MemoryRouter><ConnectWindow /></MemoryRouter>);
    const dialog = screen.getByRole("dialog", { hidden: true });
    expect(dialog).toHaveAttribute("open");
    fireEvent.click(screen.getByRole("button", { name: "Use the demo home for now", hidden: true }));
    expect(save).toHaveBeenCalledWith("user-1", { onboarded: true });
    expect(dialog).not.toHaveAttribute("open");
  });

  it("starts the Samsung login when SmartThings is available", async () => {
    stubConfig(true);
    profile(false);
    render(<MemoryRouter><ConnectWindow /></MemoryRouter>);
    const connect = screen.getByRole("button", { name: "Connect SmartThings", hidden: true });
    await waitFor(() => expect(connect).toBeEnabled());
    fireEvent.click(connect);
    await waitFor(() => expect(connectSmartThings).toHaveBeenCalled());
  });

  it("explains itself instead of failing when the server has no SmartThings app", async () => {
    stubConfig(false);
    profile(false);
    render(<MemoryRouter><ConnectWindow /></MemoryRouter>);
    expect(await screen.findByText(/isn't set up on this server yet/, {}, { timeout: 2000 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect SmartThings", hidden: true })).toBeDisabled();
  });

  it("stays closed for people who already chose", () => {
    stubConfig(true);
    profile(true);
    render(<MemoryRouter><ConnectWindow /></MemoryRouter>);
    expect(screen.getByRole("dialog", { hidden: true })).not.toHaveAttribute("open");
  });
});

describe("sign in", () => {
  it("checks the form before contacting the server, then signs in", async () => {
    auth.state = { status: "signed_out" };
    render(<MemoryRouter><SignIn /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "not-an-email" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(signIn).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "person@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct horse" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(signIn).toHaveBeenCalledWith("person@example.com", "correct horse"));
  });
});
