import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

/**
 * Clock — an analog clock whose second hand steps discretely once per
 * `secondsPerStep`, with an optional tick sound locked to each step.
 *
 * Why this exists: it's the canonical demonstration of frame-accurate
 * audio↔visual sync in Remotion. Both the hand's angle and every tick
 * `<Audio>` are derived from the SAME `useCurrentFrame()` counter, so the
 * sound lands on the exact frame the hand jumps — by construction, not by
 * manual timestamp tuning. Move the scene, change the fps, retime the
 * video: they stay married.
 *
 * The tick sound is passed in (`tickSound`), not bundled, so any source
 * works — a Freesound CC0 clip, an ElevenLabs/AudioGen-generated tick, etc.
 * If `tickSound` is omitted the clock is silent (visual only).
 */

interface ClockProps {
  /** Length of this clock scene in seconds. Passed automatically from the
   *  cut (out_seconds − in_seconds) by the Explainer dispatch. Determines how
   *  many ticks are scheduled. */
  durationSeconds?: number;
  /** Path to a tick sound effect (public/-relative or file://). One instance
   *  fires per step. Omit for a silent clock. */
  tickSound?: string;
  tickVolume?: number;
  /** Seconds between hand steps. 1 = classic one-tick-per-second. */
  secondsPerStep?: number;
  /** Where the second hand starts, 0–59. Purely cosmetic. */
  startSecond?: number;
  accentColor?: string;
  faceColor?: string;
  handColor?: string;
  tickMarkColor?: string;
  /** Clock diameter in px. */
  size?: number;
  backgroundColor?: string;
  /** Optional label under the clock (e.g. "tick tick…"). */
  label?: string;
  labelColor?: string;
}

/** Resolve a public/-relative path to a served URL; pass through absolute/URI. */
function resolveTickSrc(src: string): string {
  if (/^(https?:|file:|data:|blob:)/.test(src) || src.startsWith("/")) {
    return src;
  }
  try {
    return staticFile(src);
  } catch {
    return src;
  }
}

export const Clock: React.FC<ClockProps> = ({
  durationSeconds = 10,
  tickSound,
  tickVolume = 1,
  secondsPerStep = 1,
  startSecond = 0,
  accentColor = "#EF4444",
  faceColor = "#F8FAFC",
  handColor = "#0F172A",
  tickMarkColor = "#94A3B8",
  size = 520,
  backgroundColor = "transparent",
  label,
  labelColor = "#64748B",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const step = Math.max(0.05, secondsPerStep);
  const elapsed = frame / fps;

  // Which discrete step are we on, and how long since that step landed.
  const stepIndex = Math.floor(elapsed / step);
  const stepStartFrame = stepIndex * step * fps;
  const framesSinceStep = frame - stepStartFrame;

  // Second-hand angle: each step advances the hand by (step) seconds' worth
  // of rotation. A real second hand moves 6° per second.
  const secondValue = (startSecond + stepIndex * step) % 60;
  const baseAngle = secondValue * 6; // degrees, 0 = 12 o'clock

  // A real ticking hand overshoots slightly then settles — a small damped
  // oscillation over the first ~0.18s after each step sells the "tick".
  const settleFrames = 0.18 * fps;
  const overshoot =
    framesSinceStep < settleFrames
      ? Math.sin((framesSinceStep / settleFrames) * Math.PI * 2) *
        interpolate(framesSinceStep, [0, settleFrames], [3.2, 0], {
          extrapolateRight: "clamp",
        })
      : 0;
  const secondAngle = baseAngle + overshoot;

  // Minute/hour hands drift smoothly for a touch of life.
  const minuteAngle = (elapsed / 60) * 6;
  const hourAngle = (elapsed / 3600) * 30 + minuteAngle / 12;

  const r = size / 2;
  const center = r;

  // Schedule one tick sound per step across the scene's duration.
  const totalTicks = tickSound
    ? Math.max(0, Math.floor(durationSeconds / step) + 1)
    : 0;

  const hourMarks = Array.from({ length: 12 }, (_, i) => i);

  return (
    <AbsoluteFill
      style={{
        background: backgroundColor,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 40,
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ filter: "drop-shadow(0 12px 32px rgba(15,23,42,0.25))" }}
      >
        {/* Face */}
        <circle cx={center} cy={center} r={r - 8} fill={faceColor} />
        <circle
          cx={center}
          cy={center}
          r={r - 8}
          fill="none"
          stroke={handColor}
          strokeWidth={6}
          opacity={0.9}
        />

        {/* Hour marks */}
        {hourMarks.map((h) => {
          const a = (h * 30 - 90) * (Math.PI / 180);
          const inner = r - (h % 3 === 0 ? 44 : 30);
          const outer = r - 20;
          return (
            <line
              key={h}
              x1={center + Math.cos(a) * inner}
              y1={center + Math.sin(a) * inner}
              x2={center + Math.cos(a) * outer}
              y2={center + Math.sin(a) * outer}
              stroke={tickMarkColor}
              strokeWidth={h % 3 === 0 ? 8 : 4}
              strokeLinecap="round"
            />
          );
        })}

        {/* Hour hand */}
        <line
          x1={center}
          y1={center}
          x2={center}
          y2={center - r * 0.42}
          stroke={handColor}
          strokeWidth={14}
          strokeLinecap="round"
          transform={`rotate(${hourAngle} ${center} ${center})`}
        />
        {/* Minute hand */}
        <line
          x1={center}
          y1={center}
          x2={center}
          y2={center - r * 0.62}
          stroke={handColor}
          strokeWidth={10}
          strokeLinecap="round"
          transform={`rotate(${minuteAngle} ${center} ${center})`}
        />
        {/* Second hand (the ticking one) */}
        <line
          x1={center}
          y1={center + r * 0.14}
          x2={center}
          y2={center - r * 0.74}
          stroke={accentColor}
          strokeWidth={5}
          strokeLinecap="round"
          transform={`rotate(${secondAngle} ${center} ${center})`}
        />
        {/* Center cap */}
        <circle cx={center} cy={center} r={14} fill={accentColor} />
        <circle cx={center} cy={center} r={6} fill={faceColor} />
      </svg>

      {label && (
        <div
          style={{
            fontFamily: "Inter, system-ui, sans-serif",
            fontSize: 42,
            fontWeight: 600,
            color: labelColor,
            letterSpacing: "0.02em",
          }}
        >
          {label}
        </div>
      )}

      {/* Tick sounds — one per step, each locked to the frame the hand jumps. */}
      {tickSound &&
        Array.from({ length: totalTicks }, (_, k) => (
          <Sequence key={`tick-${k}`} from={Math.round(k * step * fps)}>
            <Audio src={resolveTickSrc(tickSound)} volume={tickVolume} />
          </Sequence>
        ))}
    </AbsoluteFill>
  );
};
