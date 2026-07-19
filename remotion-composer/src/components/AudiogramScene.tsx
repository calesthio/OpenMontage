import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { useAudioData, visualizeAudio } from "@remotion/media-utils";

export type AudiogramStyle = "bars" | "line" | "circle";
export type AudiogramPosition = "center" | "bottom" | "top";

export interface AudiogramSceneProps {
  /** Resolved URL of the audio track to visualize (same track as the music layer). */
  audioSrc: string;
  /** Visualization style. Default "bars". */
  audiogramStyle?: AudiogramStyle;
  /** Where the visualization sits in the frame. Default "center". */
  position?: AudiogramPosition;
  /** Bar/line/ring color. Default "#F59E0B". */
  color?: string;
  /** Background fill. Default "transparent" so it can overlay a reel. */
  backgroundColor?: string;
  /**
   * Number of frequency bands. MUST be a power of two. Default 256.
   * The scene shows the lower half (the audible/musical bands look best).
   */
  numberOfSamples?: number;
  /** How many of the lower bands to actually draw. Default 64. */
  bars?: number;
  /** Amplitude multiplier. Higher = taller bars. Default 6. */
  gain?: number;
  /**
   * Seconds into the track where THIS scene begins, so the visualization
   * lines up with what's actually audible. Match your music offset. Default 0.
   */
  audioOffsetSeconds?: number;
  /** Fade the whole visualization in over this many frames. Default 8. */
  fadeInFrames?: number;
}

export const AudiogramScene: React.FC<AudiogramSceneProps> = ({
  audioSrc,
  audiogramStyle = "bars",
  position = "center",
  color = "#F59E0B",
  backgroundColor = "transparent",
  numberOfSamples = 256,
  bars = 64,
  gain = 6,
  audioOffsetSeconds = 0,
  fadeInFrames = 8,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const audioData = useAudioData(audioSrc);

  const justify =
    position === "top" ? "flex-start" : position === "bottom" ? "flex-end" : "center";

  // While audio metadata loads, render an empty frame (useAudioData manages delayRender).
  if (!audioData) {
    return <AbsoluteFill style={{ background: backgroundColor }} />;
  }

  const visFrame = frame + Math.round(audioOffsetSeconds * fps);
  const spectrum = visualizeAudio({
    fps,
    frame: visFrame,
    audioData,
    numberOfSamples,
  });

  // Lower bands carry the musical energy; take the first `bars` of them.
  const values = spectrum.slice(0, Math.min(bars, spectrum.length));
  const opacity = interpolate(frame, [0, fadeInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: backgroundColor,
        justifyContent: justify,
        alignItems: "center",
        opacity,
      }}
    >
      {audiogramStyle === "circle" ? (
        <CircleViz values={values} color={color} gain={gain} width={width} height={height} />
      ) : audiogramStyle === "line" ? (
        <LineViz values={values} color={color} gain={gain} width={width} />
      ) : (
        <BarsViz values={values} color={color} gain={gain} />
      )}
    </AbsoluteFill>
  );
};

// --- Mirrored spectrum bars (the default, most reel-friendly look) ---
const BarsViz: React.FC<{ values: number[]; color: string; gain: number }> = ({
  values,
  color,
  gain,
}) => {
  // Mirror so the spectrum reads left→right→left, like a classic audiogram.
  const mirrored = [...values].reverse().concat(values);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 4,
        height: "40%",
        width: "82%",
      }}
    >
      {mirrored.map((v, i) => {
        const h = Math.min(100, v * gain * 100);
        return (
          <div
            key={i}
            style={{
              flex: 1,
              height: `${Math.max(2, h)}%`,
              background: color,
              borderRadius: 999,
              alignSelf: "center",
            }}
          />
        );
      })}
    </div>
  );
};

// --- Smooth polyline waveform ---
const LineViz: React.FC<{ values: number[]; color: string; gain: number; width: number }> = ({
  values,
  color,
  gain,
  width,
}) => {
  const h = 260;
  const step = width / Math.max(1, values.length - 1);
  const points = values
    .map((v, i) => {
      const y = h / 2 - Math.min(h / 2, v * gain * h) * (i % 2 === 0 ? 1 : -1);
      return `${i * step},${y}`;
    })
    .join(" ");
  return (
    <svg width={width} height={h} viewBox={`0 0 ${width} ${h}`}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={4}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
};

// --- Radial ring that pulses outward from center ---
const CircleViz: React.FC<{
  values: number[];
  color: string;
  gain: number;
  width: number;
  height: number;
}> = ({ values, color, gain, width, height }) => {
  const cx = width / 2;
  const cy = height / 2;
  const baseR = Math.min(width, height) * 0.18;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      {values.map((v, i) => {
        const angle = (i / values.length) * Math.PI * 2 - Math.PI / 2;
        const len = Math.min(baseR, v * gain * baseR);
        const x1 = cx + Math.cos(angle) * baseR;
        const y1 = cy + Math.sin(angle) * baseR;
        const x2 = cx + Math.cos(angle) * (baseR + len);
        const y2 = cy + Math.sin(angle) * (baseR + len);
        return (
          <line
            key={i}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke={color}
            strokeWidth={4}
            strokeLinecap="round"
          />
        );
      })}
    </svg>
  );
};
