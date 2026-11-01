import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * ProviderChip — rotating pill of AI video provider names that cycle through.
 * Positioned in a corner over background video.
 */

interface ProviderChipProps {
  providers: string[];
  cycleSeconds?: number;
  position?: "top-left" | "top-right" | "bottom-left" | "bottom-right";
  accentColor?: string;
  label?: string;
}

const POS_STYLES: Record<string, React.CSSProperties> = {
  "top-left": { top: 48, left: 48 },
  "top-right": { top: 48, right: 48 },
  "bottom-left": { bottom: 96, left: 48 },  // avoid caption zone
  "bottom-right": { bottom: 96, right: 48 },
};

export const ProviderChip: React.FC<ProviderChipProps> = ({
  providers,
  cycleSeconds = 2.5,
  position = "bottom-right",
  accentColor = "#22D3EE",
  label = "generated with",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const cycleFrames = Math.max(1, Math.round(cycleSeconds * fps));
  const idx = Math.floor(frame / cycleFrames) % providers.length;
  const current = providers[idx];
  const framesIntoCycle = frame % cycleFrames;

  // Spring in on cycle start
  const springIn = spring({
    frame: framesIntoCycle,
    fps,
    config: { damping: 14, stiffness: 200 },
    durationInFrames: Math.ceil(fps * 0.35),
  });

  // Fade out before cycle end
  const fadeOut =
    framesIntoCycle > cycleFrames - fps * 0.25
      ? interpolate(framesIntoCycle, [cycleFrames - fps * 0.25, cycleFrames], [1, 0], { extrapolateRight: "clamp" })
      : 1;

  const alpha = Math.min(springIn, fadeOut);
  const translateY = interpolate(springIn, [0, 1], [12, 0]);

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          ...POS_STYLES[position],
          display: "flex",
          flexDirection: "column",
          alignItems: position.includes("right") ? "flex-end" : "flex-start",
          gap: 8,
          opacity: alpha,
          transform: `translateY(${translateY}px)`,
        }}
      >
        <div
          style={{
            fontSize: 16,
            color: "rgba(255,255,255,0.6)",
            fontFamily: "Inter, sans-serif",
            fontWeight: 500,
            letterSpacing: 1.5,
            textTransform: "uppercase",
          }}
        >
          {label}
        </div>
        <div
          style={{
            padding: "14px 26px",
            background: "rgba(11, 15, 26, 0.82)",
            border: `2px solid ${accentColor}`,
            borderRadius: 999,
            color: accentColor,
            fontFamily: "'Space Grotesk', Inter, sans-serif",
            fontWeight: 700,
            fontSize: 28,
            letterSpacing: 0.3,
            backdropFilter: "blur(8px)",
            boxShadow: `0 8px 32px ${accentColor}30`,
          }}
        >
          {current}
        </div>
      </div>
    </AbsoluteFill>
  );
};
