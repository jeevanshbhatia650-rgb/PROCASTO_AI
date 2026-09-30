import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/config", () => ({
  loadConfig: vi.fn(async () => ({ accounts: true, supabase_url: "u", supabase_publishable_key: "k", smartthings: true, llm: "templates" })),
}));
vi.mock("../lib/connections", async (original) => ({
  ...(await original<typeof import("../lib/connections")>()),
  listConnections: vi.fn(async () => []),
  connectSmartThings: vi.fn(async () => {}),
  disconnectSmartThings: vi.fn(async () => {}),
}));
vi.mock("../lib/account", async (original) => ({
  ...(await original<typeof import("../lib/account")>()),
  deleteAccount: vi.fn(async () => {}),
  signOut: vi.fn(async () => {}),
}));
vi.mock("../lib/auth", () => ({
  useAuth: () => ({ status: "signed_in", session: { user: { id: "user-1", email: "neha@example.invalid" } } }),
}));

import { deleteAccount, useProfile } from "../lib/account";
import { connectSmartThings, disconnectSmartThings, listConnections } from "../lib/connections";
import IntegrationsPage from "./app/IntegrationsPage";
import ProfilePage from "./app/ProfilePage";

beforeEach(() => {
  vi.clearAllMocks();
  act(() =>
    useProfile.setState({
      status: "ready",
      profile: { display_name: "Neha", home_name: "Riverside flat", onboarded: true, created_at: "2026-09-30T00:00:00Z" },
    }),
  );
});

describe("integrations", () => {
  it("offers to connect SmartThings and is honest about the rest", async () => {
    render(<MemoryRouter><IntegrationsPage /></MemoryRouter>);
    const connect = await screen.findByRole("button", { name: "Connect SmartThings" });
    await waitFor(() => expect(connect).toBeEnabled());
    expect(screen.getByText("Exploring")).toBeInTheDocument();
    fireEvent.click(connect);
    await waitFor(() => expect(connectSmartThings).toHaveBeenCalled());
  });

  it("shows the result of the Samsung login and a two-step disconnect", async () => {
    vi.mocked(listConnections).mockResolvedValue([
      { provider: "smartthings", status: "connected", account_label: "Samsung account", connected_at: "2026-09-30T00:00:00Z" },
    ]);
    render(<MemoryRouter initialEntries={["/app/integrations?smartthings=connected"]}><IntegrationsPage /></MemoryRouter>);
    expect(await screen.findByText(/SmartThings is connected/)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Disconnect" }));
    expect(disconnectSmartThings).not.toHaveBeenCalled(); // first click only asks
    fireEvent.click(screen.getByRole("button", { name: "Disconnect" }));
    await waitFor(() => expect(disconnectSmartThings).toHaveBeenCalled());
  });
});

describe("profile", () => {
  it("shows who you are and only deletes after DELETE is typed", async () => {
    render(<MemoryRouter><ProfilePage /></MemoryRouter>);
    expect(screen.getByText("neha@example.invalid")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Riverside flat")).toBeInTheDocument();
    const remove = screen.getByRole("button", { name: /Delete my account/ });
    expect(remove).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Type DELETE to confirm"), { target: { value: "delete" } });
    expect(remove).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Type DELETE to confirm"), { target: { value: "DELETE" } });
    fireEvent.click(remove);
    await waitFor(() => expect(deleteAccount).toHaveBeenCalled());
  });
});
