import { describe, expect, it } from "vitest";

import { correlationColor, DIVERGING, SERIES, seriesColor } from "./palette";

describe("palette", () => {
  it("assigns categorical slots in fixed order", () => {
    expect(seriesColor(0, "light")).toBe(SERIES.light[0]);
    expect(seriesColor(2, "light")).toBe(SERIES.light[2]);
  });

  it("never generates a hue past the last slot", () => {
    const last = SERIES.light[SERIES.light.length - 1];
    expect(seriesColor(99, "light")).toBe(last);
  });

  it("keeps light and dark as the same number of selected steps", () => {
    expect(SERIES.dark).toHaveLength(SERIES.light.length);
  });

  it("does not reuse a light value in dark mode without re-stepping", () => {
    // Green is deliberately mode-invariant; everything else is re-stepped.
    const shared = SERIES.light.filter((hex, i) => hex === SERIES.dark[i]);
    expect(shared).toEqual(["#008300"]);
  });
});

describe("correlationColor", () => {
  it("returns the neutral midpoint at zero", () => {
    expect(correlationColor(0, "light")).toBe(DIVERGING.light.midpoint);
  });

  it("saturates toward opposite poles for opposite signs", () => {
    expect(correlationColor(1, "light")).toBe(DIVERGING.light.positive);
    expect(correlationColor(-1, "light")).toBe(DIVERGING.light.negative);
  });

  it("gives negative and positive correlation visibly different colours", () => {
    // A single-hue ramp would make -0.8 and +0.8 look alike, which is the
    // whole reason the scale is diverging.
    expect(correlationColor(-0.8, "light")).not.toBe(correlationColor(0.8, "light"));
  });

  it("handles a null cell without producing a colour", () => {
    expect(correlationColor(null, "light")).toBe("transparent");
  });
});
