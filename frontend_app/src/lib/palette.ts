/**
 * Chart palette.
 *
 * Both modes are *selected*, not derived: the dark column is the same eight
 * hues re-stepped for the dark surface, never an automatic flip of the light
 * values. Slots are assigned in fixed order and never cycled.
 *
 * Validated with the dataviz validator against both surfaces:
 *   light  worst adjacent CVD dE 9.1, normal-vision dE 19.6  (PASS)
 *   dark   worst adjacent CVD dE 8.4, normal-vision dE 19.3  (PASS)
 *
 * Light mode WARNs on contrast for aqua, yellow, and magenta (all below 3:1
 * against the light surface). The relief rule applies and is satisfied: every
 * answer ships a Table tab, so no value is ever carried by color alone.
 */

export type Mode = "light" | "dark";

/** Categorical slots, in fixed assignment order. */
export const SERIES: Record<Mode, string[]> = {
  light: [
    "#2a78d6", // 1 blue
    "#eb6834", // 2 orange
    "#1baf7a", // 3 aqua
    "#eda100", // 4 yellow
    "#e87ba4", // 5 magenta
    "#008300", // 6 green
    "#4a3aa7", // 7 violet
    "#e34948", // 8 red
  ],
  dark: [
    "#3987e5",
    "#d95926",
    "#199e70",
    "#c98500",
    "#d55181",
    "#008300",
    "#9085e9",
    "#e66767",
  ],
};

/**
 * Scatter, bubble, and heatmap read every pair at once rather than only
 * neighbours, and the full eight cannot clear the floors under all-pairs.
 * The first three slots do, in both modes.
 */
export const ALL_PAIRS_SERIES_CAP = 3;

/** Diverging poles for the correlation heatmap: -1 blue, 0 gray, +1 red. */
export const DIVERGING: Record<Mode, { negative: string; midpoint: string; positive: string }> = {
  light: { negative: "#2a78d6", midpoint: "#f0efec", positive: "#e34948" },
  dark: { negative: "#3987e5", midpoint: "#383835", positive: "#e66767" },
};

/** Chart chrome. Text never wears a series color. */
export const CHROME: Record<
  Mode,
  {
    surface: string;
    textPrimary: string;
    textSecondary: string;
    muted: string;
    grid: string;
    axis: string;
  }
> = {
  light: {
    surface: "#fcfcfb",
    textPrimary: "#0b0b0b",
    textSecondary: "#52514e",
    muted: "#898781",
    grid: "#e1e0d9",
    axis: "#c3c2b7",
  },
  dark: {
    surface: "#1a1a19",
    textPrimary: "#ffffff",
    textSecondary: "#c3c2b7",
    muted: "#898781",
    grid: "#2c2c2a",
    axis: "#383835",
  },
};

/** Severity colors for the insights panel. Always shipped with a label. */
export const STATUS = {
  high: "#d03b3b",
  medium: "#ec835a",
  low: "#898781",
} as const;

export function seriesColor(index: number, mode: Mode): string {
  const slots = SERIES[mode];
  // Never generate a hue. Past the last slot the caller should have folded
  // into "Other" or faceted; clamping is the safe fallback.
  return slots[Math.min(index, slots.length - 1)];
}

/**
 * Map a correlation coefficient onto the diverging ramp.
 * Gray at zero, saturating toward each pole.
 */
export function correlationColor(value: number | null, mode: Mode): string {
  const { negative, midpoint, positive } = DIVERGING[mode];
  if (value === null || Number.isNaN(value)) return "transparent";

  const magnitude = Math.min(Math.abs(value), 1);
  const pole = value < 0 ? negative : positive;
  return mixHex(midpoint, pole, magnitude);
}

function mixHex(from: string, to: string, amount: number): string {
  const a = hexToRgb(from);
  const b = hexToRgb(to);
  const channel = (x: number, y: number) => Math.round(x + (y - x) * amount);
  return rgbToHex(channel(a[0], b[0]), channel(a[1], b[1]), channel(a[2], b[2]));
}

function hexToRgb(hex: string): [number, number, number] {
  const value = hex.replace("#", "");
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16),
  ];
}

function rgbToHex(r: number, g: number, b: number): string {
  return `#${[r, g, b].map((c) => c.toString(16).padStart(2, "0")).join("")}`;
}
