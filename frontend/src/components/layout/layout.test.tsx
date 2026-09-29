import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useStore } from "../../lib/store";
import { HoodToggle } from "./HoodToggle";
import { SplitPane } from "./SplitPane";

function Layout() {
  const open = useStore((s) => s.hoodOpen);
  return (
    <>
      <HoodToggle />
      <SplitPane hoodOpen={open} left={<p>user view</p>} right={<p>engine view</p>} />
    </>
  );
}

describe("under-the-hood toggle (F21)", () => {
  it("starts on the clean user view", () => {
    act(() => useStore.setState({ hoodOpen: false }));
    render(<Layout />);
    expect(screen.getByText("user view")).toBeInTheDocument();
    expect(screen.queryByText("engine view")).not.toBeInTheDocument();
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false");
  });

  it("opens the engine view beside the user view", () => {
    act(() => useStore.setState({ hoodOpen: false }));
    render(<Layout />);
    fireEvent.click(screen.getByRole("switch"));
    expect(screen.getByText("engine view")).toBeInTheDocument();
    expect(screen.getByText("user view")).toBeInTheDocument();
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
  });
});
