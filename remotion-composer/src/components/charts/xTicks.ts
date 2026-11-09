// LineChart's x axis. x values are coordinates, often years: evenly spaced fractions of
// 1990..2024 printed "2.0K" on every tick.

/**
 * Evenly spaced ticks across the x range, as before. When every x is an integer the
 * ticks are rounded to integers too, so years and counts never get fractional ticks.
 */
export function pickXTicks(xs: number[], maxIntervals = 6): number[] {
  if (xs.length === 0) return [];
  const min = Math.min(...xs);
  const max = Math.max(...xs);
  const intervals = Math.min(xs.length - 1, maxIntervals);
  if (intervals < 1 || min === max) return [min];
  const ticks = Array.from({ length: intervals + 1 }, (_, i) => min + ((max - min) / intervals) * i);
  return xs.every(Number.isInteger) ? Array.from(new Set(ticks.map(Math.round))) : ticks;
}

/** An integer below 10 000 is written as is, so 2020 never becomes "2.0K". */
export function formatXTick(n: number, format: (n: number) => string): string {
  return Number.isInteger(n) && Math.abs(n) < 10_000 ? String(n) : format(n);
}
