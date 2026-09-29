import { describe, expect, it } from "vitest";
import { clearOf, labelWidth, placeLabels } from "./labels";

const W = 360; // chart width in px, as in the recorded 1440px frames

describe("timeline label placement", () => {
  it("puts labels right of their marks and hides one that would overlap the previous label", () => {
    expect(placeLabels([0, 2, 50], ["How", "long", "washer"], W)).toEqual(["right", null, "right"]);
  });

  it("flips a label to the left near the right edge", () => {
    expect(placeLabels([95], ["dryer"], W)).toEqual(["left"]);
  });

  it("moves a label left rather than cover the next mark when marks must stay readable", () => {
    // The fault moment: "washer · status" then, 0.4 s later, the auto "washer · E3" lookup.
    const sides = placeLabels([37, 55], ["washer · status", "washer · E3"], W, true);
    expect(sides).toEqual(["left", "right"]);
  });

  it("hides a label that fits on neither side", () => {
    expect(placeLabels([10, 12], ["washer · status", "washer · E3"], W, true)).toEqual([null, "right"]);
  });
});

describe("axis ticks around the finish line", () => {
  const finish = labelWidth("you finished");

  it("hides a tick under a label flipped to the left of the line", () => {
    // The correction frame: "1.0 s" sat under "you finished".
    expect(clearOf(231, 293, finish, "left")).toBe(false);
  });

  it("keeps ticks well clear of the label", () => {
    expect(clearOf(39, 293, finish, "left")).toBe(true);
    expect(clearOf(250, 100, finish, "right")).toBe(true);
  });
});
