// Music ducking under narration for the Explainer composition.
//
// `audio.music.ducking` used to be accepted by the pipeline skills and ignored
// here: music played at one flat level under the voice. Speech intervals come
// from the word captions when they exist (merged across short pauses), else
// the narration is assumed to run for the whole composition.

export type DuckingOptions = {
  /** Music gain while speech plays, as a fraction of the base volume. */
  duckedGain?: number;
  /** Seconds to fall to the ducked gain before speech starts. */
  attackSeconds?: number;
  /** Seconds to recover to full gain after speech ends. */
  releaseSeconds?: number;
  /** Pauses shorter than this stay ducked (no pumping between words). */
  mergeGapSeconds?: number;
};

export type DuckingSetting = boolean | DuckingOptions | undefined;

export type SpeechInterval = { start: number; end: number };

export const DUCKING_DEFAULTS: Required<DuckingOptions> = {
  duckedGain: 0.35,
  attackSeconds: 0.15,
  releaseSeconds: 0.4,
  mergeGapSeconds: 0.6,
};

export function resolveDucking(setting: DuckingSetting): Required<DuckingOptions> | null {
  if (!setting) return null;
  if (setting === true) return { ...DUCKING_DEFAULTS };
  return { ...DUCKING_DEFAULTS, ...setting };
}

/** Merge caption word timings (ms) into speech intervals (seconds). */
export function speechIntervalsFromCaptions(
  captions: { startMs: number; endMs: number }[],
  mergeGapSeconds: number,
): SpeechInterval[] {
  const words = captions
    .filter((c) => Number.isFinite(c.startMs) && Number.isFinite(c.endMs) && c.endMs > c.startMs)
    .map((c) => ({ start: c.startMs / 1000, end: c.endMs / 1000 }))
    .sort((a, b) => a.start - b.start);
  const out: SpeechInterval[] = [];
  for (const w of words) {
    const last = out[out.length - 1];
    if (last && w.start - last.end <= mergeGapSeconds) {
      last.end = Math.max(last.end, w.end);
    } else {
      out.push({ ...w });
    }
  }
  return out;
}

/** Gain multiplier (duckedGain..1) for the music at time `t` seconds. */
export function duckGainAt(
  t: number,
  intervals: SpeechInterval[],
  options: Required<DuckingOptions>,
): number {
  const { duckedGain, attackSeconds, releaseSeconds } = options;
  let gain = 1;
  for (const { start, end } of intervals) {
    let g = 1;
    if (t >= start && t <= end) {
      g = duckedGain;
    } else if (t < start && t >= start - attackSeconds) {
      g = 1 - (1 - duckedGain) * ((t - (start - attackSeconds)) / attackSeconds);
    } else if (t > end && t <= end + releaseSeconds) {
      g = duckedGain + (1 - duckedGain) * ((t - end) / releaseSeconds);
    }
    gain = Math.min(gain, g);
  }
  return gain;
}
