/** Pixel layout for the timeline's text labels, so they don't overlap each other or the marks they describe. */

const CHAR_PX = 6.6; // average width of a 12px label character
const LABEL_GAP_PX = 10;
const TICK_HALF_PX = 3 * CHAR_PX; // an axis label like "1.5 s" is centred on its tick
export const FLIP_AT_PCT = 72;

export type Side = "right" | "left" | null;

export const labelWidth = (text: string) => text.length * CHAR_PX + LABEL_GAP_PX;

/**
 * Puts each label right of its mark, or left of it near the right edge or when the right is taken, or hides it when
 * neither side fits. With avoidMarks a label may not cover another mark either: on sparse rows every mark matters.
 */
export function placeLabels(positions: number[], labels: string[], widthPx: number, avoidMarks = false): Side[] {
  const xs = positions.map((pct) => (pct / 100) * widthPx);
  let freeFromPx = Number.NEGATIVE_INFINITY;
  return xs.map((x, i) => {
    const w = labelWidth(labels[i] ?? "");
    const covers = (from: number, to: number) => avoidMarks && xs.some((m, j) => j !== i && m > from && m < to);
    const order: Side[] = (positions[i] ?? 0) > FLIP_AT_PCT ? ["left", "right"] : ["right", "left"];
    for (const side of order) {
      const [from, to] = side === "right" ? [x, x + w] : [x - w, x];
      if (from >= freeFromPx && from >= 0 && to <= widthPx + 4 && !covers(from, to)) {
        freeFromPx = to;
        return side;
      }
    }
    return null;
  });
}

/** Whether an axis label at tickPx stays clear of a label labelPx wide drawn from anchorPx towards side. */
export function clearOf(tickPx: number, anchorPx: number, labelPx: number, side: "left" | "right"): boolean {
  const [from, to] = side === "left" ? [anchorPx - labelPx, anchorPx] : [anchorPx, anchorPx + labelPx];
  return tickPx + TICK_HALF_PX < from || tickPx - TICK_HALF_PX > to;
}
