// Show amounts the way a recipe card does: 1.5 -> "1 1/2", 0.333 -> "1/3".
const NICE: [number, string][] = [
  [1 / 8, "1/8"], [1 / 4, "1/4"], [1 / 3, "1/3"], [3 / 8, "3/8"], [1 / 2, "1/2"],
  [5 / 8, "5/8"], [2 / 3, "2/3"], [3 / 4, "3/4"], [7 / 8, "7/8"],
];

export function formatQuantity(value: number | null | undefined): string {
  if (value === null || value === undefined) return "";
  const whole = Math.floor(value);
  const frac = value - whole;
  if (frac < 0.02) return String(whole);
  if (frac > 0.98) return String(whole + 1);
  for (const [target, label] of NICE) {
    if (Math.abs(frac - target) < 0.02) return whole ? `${whole} ${label}` : label;
  }
  return value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

type Line = {
  raw_text: string;
  quantity?: number | null;
  quantity_max?: number | null;
  unit?: string | null;
  name?: string | null;
  note?: string | null;
};

// Rewrite an ingredient line for a different batch size. Lines without a
// parsed amount ("salt to taste") are shown as typed.
export function scaleLine(line: Line, factor: number): string {
  if (factor === 1 || line.quantity == null || !line.name) return line.raw_text;
  let amount = formatQuantity(line.quantity * factor);
  if (line.quantity_max != null) amount += `–${formatQuantity(line.quantity_max * factor)}`;
  const top = line.quantity_max ?? line.quantity;
  const unit = line.unit && top * factor > 1 && PLURAL[line.unit] ? PLURAL[line.unit] : line.unit;
  const parts = [amount, unit, line.name].filter(Boolean).join(" ");
  return line.note ? `${parts}, ${line.note}` : parts;
}

// Spelled-out units read better in the plural; abbreviations (tsp, oz) stay as they are.
const PLURAL: Record<string, string> = {
  cup: "cups", pint: "pints", quart: "quarts", gallon: "gallons", stick: "sticks", can: "cans", jar: "jars",
  package: "packages", box: "boxes", bag: "bags", pinch: "pinches", dash: "dashes", drop: "drops",
  clove: "cloves", slice: "slices", piece: "pieces", bunch: "bunches", head: "heads", sprig: "sprigs",
  handful: "handfuls", square: "squares",
};
