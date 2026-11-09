// Number formatting for the chart components.
//
// A KPI keeps the precision it was written with. Rounding the count-up to an integer
// showed 1.76 as "2", and remotion's spring settles at 0.9999999999999998, so 12.5
// stayed at "12" on every frame.

/** Decimal places a value is written with; 20 is the limit of toFixed. */
export const decimalsOf = (n: number): number => {
  if (!Number.isFinite(n) || Number.isInteger(n)) return 0;
  const [mantissa, exponent] = String(n).split("e");
  const fraction = (mantissa.split(".")[1] ?? "").length;
  return Math.min(Math.max(fraction - Number(exponent ?? 0), 0), 20);
};

/** KPI counter at `progress` (0..1). Scale and digits come from the target, so they never jump. */
export function formatKpiValue(target: number, progress: number): string {
  const decimals = decimalsOf(target);
  const factor = 10 ** decimals;
  const current = Math.round(target * progress * factor) / factor;
  if (target >= 1_000_000) return `${(current / 1_000_000).toFixed(1)}M`;
  if (target >= 1_000) return `${(current / 1_000).toFixed(1)}K`;
  return current.toFixed(decimals);
}
