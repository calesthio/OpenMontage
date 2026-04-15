import {
  AbsoluteFill,
  CalculateMetadataFunction,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { getVideoMetadata } from "@remotion/media-utils";
import { loadFont } from "@remotion/google-fonts/PlayfairDisplay";

// Editorial serif for the tagline — Playfair Display at its boldest weight.
// Loaded once at module scope so every render reuses the same font face.
const { fontFamily } = loadFont("normal", {
  weights: ["400", "700", "900"],
  subsets: ["latin"],
});

export interface TitledVideoProps {
  videoSrc: string;
  tagline: string;
  // When the tagline starts animating in, in seconds from the start of the video.
  taglineInSeconds: number;
  // When the tagline should be fully gone. If omitted, it holds to the end of the clip.
  taglineOutSeconds?: number;
  // Pixels from the top of the frame where the tagline sits. Upper-third by default.
  topPx?: number;
  // Optional override for the font size.
  fontSize?: number;
  // Accent color used for the underline and the glow halo.
  accentColor?: string;
}

// Resolve asset path — handle URLs, absolute paths, and public/ relative paths.
// Mirrors the helper in Explainer.tsx so absolute Windows/Unix paths work.
function resolveAsset(src: string): string {
  if (
    src.startsWith("http://") ||
    src.startsWith("https://") ||
    src.startsWith("data:")
  ) {
    return src;
  }
  const clean = src.replace(/^file:\/\/\/?/, "");
  if (clean.startsWith("/") || /^[A-Za-z]:[\\/]/.test(clean)) {
    return `file:///${clean.replace(/\\/g, "/")}`;
  }
  return staticFile(clean);
}

// ---------------------------------------------------------------------------
// EditorialTagline — big bold serif, upper-third, drawn underline, warm glow.
// Letter-by-letter spring entrance. Designed to feel like a printed headline,
// not a subtitle.
// ---------------------------------------------------------------------------
const EditorialTagline: React.FC<{
  text: string;
  topPx: number;
  fontSize: number;
  accentColor: string;
}> = ({ text, topPx, fontSize, accentColor }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const chars = text.split("");

  // Hold the title until the last 8 frames, then ease out.
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 10, durationInFrames - 2],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Underline sweeps in after ~12 frames so the eye lands on the words first.
  const underline = spring({
    frame: frame - 12,
    fps,
    config: { damping: 18, stiffness: 70 },
  });

  // Glow pulses gently on a long period so the shine reads without flickering.
  const glowPulse =
    0.6 + 0.4 * Math.sin((frame / fps) * Math.PI * 0.6);

  // Width target for the underline — measured in CSS px.
  // We let it grow up to 70% of a max line width so it visually underscores
  // the phrase no matter how many characters the tagline has.
  const estimatedTextWidth = Math.min(
    chars.length * fontSize * 0.48,
    1600
  );

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-start",
        alignItems: "center",
        pointerEvents: "none",
      }}
    >
      {/* Soft top-of-frame darkening so the bright type sits on a scrim
          without covering the whole video. Gradient fades out by ~35% */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to bottom, rgba(10,8,6,0.55) 0%, rgba(10,8,6,0.25) 22%, rgba(10,8,6,0) 40%)",
          opacity: fadeOut,
        }}
      />
      <div
        style={{
          position: "absolute",
          top: topPx,
          left: 0,
          right: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          opacity: fadeOut,
        }}
      >
        {/* Tagline text */}
        <div
          style={{
            fontFamily,
            fontWeight: 900,
            fontSize,
            lineHeight: 1.02,
            letterSpacing: "-0.015em",
            color: "#FFF8EC",
            textAlign: "center",
            // Warm editorial glow — double drop-shadow gives a print-ink feel.
            textShadow: `
              0 2px 0 rgba(0,0,0,0.45),
              0 8px 28px rgba(0,0,0,0.55),
              0 0 ${24 + glowPulse * 24}px ${accentColor}80,
              0 0 ${60 + glowPulse * 40}px ${accentColor}40
            `,
            display: "flex",
            justifyContent: "center",
            flexWrap: "nowrap",
            whiteSpace: "nowrap",
          }}
        >
          {chars.map((char, i) => {
            const delay = i * 1.6;
            const charSpring = spring({
              frame: frame - delay,
              fps,
              config: { damping: 14, stiffness: 140 },
            });
            const dy = interpolate(charSpring, [0, 1], [38, 0]);
            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  opacity: charSpring,
                  transform: `translateY(${dy}px)`,
                  whiteSpace: char === " " ? "pre" : undefined,
                  minWidth: char === " " ? "0.28em" : undefined,
                }}
              >
                {char}
              </span>
            );
          })}
        </div>

        {/* Animated underline — draws in from the center outward */}
        <div
          style={{
            marginTop: Math.round(fontSize * 0.18),
            height: Math.max(4, Math.round(fontSize * 0.055)),
            width: estimatedTextWidth * underline,
            background: `linear-gradient(90deg, ${accentColor}00 0%, ${accentColor} 20%, ${accentColor} 80%, ${accentColor}00 100%)`,
            borderRadius: 4,
            boxShadow: `0 0 ${18 + glowPulse * 18}px ${accentColor}cc`,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// TitledVideo composition — plays a prerendered clip full-bleed and overlays
// the editorial tagline during a window of the timeline.
// ---------------------------------------------------------------------------
export const TitledVideo: React.FC<TitledVideoProps> = ({
  videoSrc,
  tagline,
  taglineInSeconds,
  taglineOutSeconds,
  topPx = 150,
  fontSize = 148,
  accentColor = "#F5C470",
}) => {
  const { fps, durationInFrames } = useVideoConfig();

  const inFrame = Math.max(0, Math.round(taglineInSeconds * fps));
  const endFrame =
    taglineOutSeconds !== undefined
      ? Math.round(taglineOutSeconds * fps)
      : durationInFrames;
  const overlayFrames = Math.max(1, endFrame - inFrame);

  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {/* Full-bleed background video — no fades, no vignette, no color shift.
          The source is already color-graded final.mp4 with music baked in;
          we play it through untouched, audio included. */}
      <OffthreadVideo
        src={resolveAsset(videoSrc)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
        }}
      />

      {/* Tagline overlay in its own Sequence so it mounts exactly on the
          fade-in frame and carries its own local frame counter. */}
      <Sequence from={inFrame} durationInFrames={overlayFrames}>
        <EditorialTagline
          text={tagline}
          topPx={topPx}
          fontSize={fontSize}
          accentColor={accentColor}
        />
      </Sequence>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// calculateMetadata — probe the source clip so the composition runs at the
// clip's native duration. Falls back to 60s at 30fps if probing fails.
// ---------------------------------------------------------------------------
export const calculateTitledVideoMetadata: CalculateMetadataFunction<
  TitledVideoProps
> = async ({ props }) => {
  try {
    const meta = await getVideoMetadata(resolveAsset(props.videoSrc));
    return {
      durationInFrames: Math.max(1, Math.round(meta.durationInSeconds * 30)),
      fps: 30,
      width: 1920,
      height: 1080,
    };
  } catch {
    return {
      durationInFrames: 30 * 60,
      fps: 30,
      width: 1920,
      height: 1080,
    };
  }
};
