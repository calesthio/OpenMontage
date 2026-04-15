import {
  AbsoluteFill,
  interpolate,
  Easing,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export interface EndTagProps {
  text: string;
  palette?: "cool_offwhite_on_black" | "warm_ivory_on_black";
  // Optional extra fade hold controls (all in seconds)
  fadeInSeconds?: number;
  holdSeconds?: number;
  fadeOutSeconds?: number;
  // Overlay mode: render on a transparent background so the tag can be
  // composited on top of the body footage in post, instead of being
  // concatenated as a standalone black card. When `overlay=true` the
  // AbsoluteFill drops its background fill — caller is responsible for
  // rendering with an alpha-capable codec (VP9/WebM or ProRes 4444).
  overlay?: boolean;
}

const PALETTES = {
  cool_offwhite_on_black: {
    background: "#000000",
    text: "#F5F7FA",
    underline: "#EAECEF",
    shine: "rgba(255,255,255,0.95)",
  },
  warm_ivory_on_black: {
    background: "#000000",
    text: "#F5EBD5",
    underline: "#E6D4A8",
    shine: "rgba(255,238,200,0.95)",
  },
} as const;

/**
 * EndTag — a philosophical closing card for documentary-montage films.
 *
 * Renders a bold, letter-spaced, uppercase line of text on a black
 * canvas with an animated underline that draws in, then receives a
 * single left-to-right shimmer pass. Fades in, holds, fades out.
 *
 * Intended usage: rendered as a standalone Remotion composition, then
 * concatenated after the FFmpeg-composed body of the montage. This
 * sidesteps the scene-adapter gap in video_compose.render and keeps
 * the two engines (FFmpeg for footage, Remotion for typography)
 * cleanly separated.
 */
export const EndTag: React.FC<EndTagProps> = ({
  text,
  palette = "cool_offwhite_on_black",
  fadeInSeconds = 0.6,
  holdSeconds = 4.3,
  fadeOutSeconds = 0.6,
  overlay = false,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const pal = PALETTES[palette];

  // Timing in frames
  const fadeInFrames = Math.round(fadeInSeconds * fps);
  const holdFrames = Math.round(holdSeconds * fps);
  const fadeOutFrames = Math.round(fadeOutSeconds * fps);

  // Full opacity envelope: fade in -> hold -> fade out
  const fadeInEnd = fadeInFrames;
  const fadeOutStart = fadeInEnd + holdFrames;
  const fadeOutEnd = fadeOutStart + fadeOutFrames;

  const opacity = interpolate(
    frame,
    [0, fadeInEnd, fadeOutStart, fadeOutEnd],
    [0, 1, 1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.inOut(Easing.ease),
    }
  );

  // Underline draws in AFTER the text has faded to full (0.2s lag),
  // and takes 0.9s to reach full width
  const underlineStartFrame = fadeInEnd + Math.round(0.2 * fps);
  const underlineDrawFrames = Math.round(0.9 * fps);
  const underlineWidthPct = interpolate(
    frame,
    [underlineStartFrame, underlineStartFrame + underlineDrawFrames],
    [0, 100],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.ease),
    }
  );

  // Shimmer pass: starts 0.3s after the underline finishes drawing,
  // travels left-to-right across the underline for 1.2s, then parks.
  const shimmerStartFrame =
    underlineStartFrame + underlineDrawFrames + Math.round(0.3 * fps);
  const shimmerTravelFrames = Math.round(1.2 * fps);
  const shimmerPosPct = interpolate(
    frame,
    [shimmerStartFrame, shimmerStartFrame + shimmerTravelFrames],
    [-40, 140],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.inOut(Easing.ease),
    }
  );
  const shimmerVisible =
    frame >= shimmerStartFrame &&
    frame <= shimmerStartFrame + shimmerTravelFrames;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: overlay ? "transparent" : pal.background,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          opacity,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          maxWidth: "86%",
        }}
      >
        {/* The tag line */}
        <div
          style={{
            fontFamily:
              "'Space Grotesk', 'Inter', 'Helvetica Neue', system-ui, sans-serif",
            fontWeight: 900,
            fontSize: 84,
            letterSpacing: "0.12em",
            lineHeight: 1.18,
            color: pal.text,
            textAlign: "center",
            textTransform: "uppercase",
            // soft drop-shadow so the letters read cleanly on black
            // without looking neon
            textShadow:
              "0 2px 12px rgba(0,0,0,0.8), 0 1px 2px rgba(0,0,0,0.6)",
          }}
        >
          {text}
        </div>

        {/* The underline — draws in, then gets a single shimmer pass */}
        <div
          style={{
            marginTop: 38,
            position: "relative",
            width: 820,
            maxWidth: "100%",
            height: 5,
          }}
        >
          {/* Underline body (width interpolates from 0 -> 100%) */}
          <div
            style={{
              position: "absolute",
              left: "50%",
              top: 0,
              transform: "translateX(-50%)",
              width: `${underlineWidthPct}%`,
              height: 5,
              backgroundColor: pal.underline,
              borderRadius: 3,
              boxShadow: `0 0 18px 0 ${pal.underline}33`,
            }}
          />

          {/* Shimmer highlight travelling across the underline */}
          {shimmerVisible && (
            <div
              style={{
                position: "absolute",
                left: `${shimmerPosPct}%`,
                top: -3,
                width: 160,
                height: 11,
                transform: "translateX(-50%)",
                background: `linear-gradient(90deg, transparent 0%, ${pal.shine} 50%, transparent 100%)`,
                filter: "blur(2px)",
                pointerEvents: "none",
              }}
            />
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};
