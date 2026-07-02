import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

type ProgressAnimationStyle = "fill" | "pulse" | "step";

interface ProgressSegment {
  value: number;
  color?: string;
  label?: string;
}

interface ProgressBarProps {
  progress: number;
  label?: string;
  color?: string;
  backgroundColor?: string;
  trackColor?: string;
  showPercentage?: boolean;
  animationStyle?: ProgressAnimationStyle;
  segments?: ProgressSegment[];
  height?: number;
  borderRadius?: number;
  fontFamily?: string;
  textColor?: string;
  labelFontSize?: number;
  percentageFontSize?: number;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  progress,
  label,
  color = "#2563EB",
  backgroundColor = "#FFFFFF",
  trackColor = "#E5E7EB",
  showPercentage = true,
  animationStyle = "fill",
  segments,
  height = 32,
  borderRadius = 8,
  fontFamily = "Inter, system-ui, sans-serif",
  textColor = "#1F2937",
  labelFontSize = 36,
  percentageFontSize = 28,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // progress is a 0-100 percentage integer (e.g. 82 = 82%).
  // Values on a 0-1 fraction scale are NOT supported — use 0-100 directly.
  const clampedProgress = Math.max(0, Math.min(100, progress));

  // Container entrance animation
  const containerOpacity = spring({
    frame,
    fps,
    config: { damping: 20 },
  });
  const containerScale = spring({
    frame,
    fps,
    config: { damping: 15, stiffness: 100 },
    from: 0.95,
    to: 1,
  });

  // Build fill width based on animation style
  let fillFraction: number;

  if (animationStyle === "fill") {
    fillFraction = interpolate(
      frame,
      [10, Math.max(30, durationInFrames * 0.5)],
      [0, clampedProgress / 100],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
  } else if (animationStyle === "pulse") {
    const base = interpolate(
      frame,
      [10, Math.max(30, durationInFrames * 0.4)],
      [0, clampedProgress / 100],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    // Subtle pulse once fill completes
    const pulsePhase = interpolate(
      frame,
      [durationInFrames * 0.4, durationInFrames * 0.9],
      [0, Math.PI * 4],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    const pulseScale =
      base >= clampedProgress / 100 - 0.01
        ? 1 + Math.sin(pulsePhase) * 0.015
        : 1;
    fillFraction = base * pulseScale;
  } else {
    // step — discrete jumps
    const stepCount = segments ? segments.length : 5;
    const rawProgress = interpolate(
      frame,
      [10, Math.max(30, durationInFrames * 0.6)],
      [0, clampedProgress / 100],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    fillFraction =
      Math.floor(rawProgress * stepCount) / stepCount;
  }

  // Percentage label spring (appears after fill starts)
  const percentOpacity = spring({
    frame: frame - 15,
    fps,
    config: { damping: 20 },
  });

  // Rendered percentage tracks fill
  const displayedPercent = Math.round(fillFraction * 100);

  // Segmented variant
  const isSegmented = segments && segments.length > 0;

  // Bar track dimensions (centered, 70% canvas width)
  const trackWidth = 1344; // 70% of 1920
  const trackLeft = (1920 - trackWidth) / 2;
  const trackTop = label ? 520 : 500;

  return (
    <AbsoluteFill
      style={{
        background: backgroundColor,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          opacity: containerOpacity,
          transform: `scale(${containerScale})`,
          width: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 24,
        }}
      >
        {/* Label */}
        {label && (
          <div
            style={{
              fontFamily,
              fontWeight: 700,
              fontSize: labelFontSize,
              color: textColor,
              textAlign: "center",
              opacity: spring({
                frame,
                fps,
                config: { damping: 20 },
              }),
            }}
          >
            {label}
          </div>
        )}

        {/* Track */}
        <div
          style={{
            width: `${(trackWidth / 1920) * 100}%`,
            position: "relative",
          }}
        >
          <div
            style={{
              width: "100%",
              height,
              backgroundColor: trackColor,
              borderRadius,
              overflow: "hidden",
              position: "relative",
              display: "flex",
            }}
          >
            {isSegmented ? (
              // Segmented bars
              segments!.map((seg, i) => {
                const segDelay = 10 + i * 8;
                const segProgress = spring({
                  frame: frame - segDelay,
                  fps,
                  config: { damping: 14, stiffness: 80 },
                });
                const segWidth = (seg.value / 100) * 100;
                return (
                  <div
                    key={i}
                    style={{
                      width: `${segWidth}%`,
                      height: "100%",
                      backgroundColor: seg.color || color,
                      transform: `scaleX(${segProgress})`,
                      transformOrigin: "left",
                      borderRight:
                        i < segments!.length - 1
                          ? `2px solid ${backgroundColor}`
                          : "none",
                    }}
                  />
                );
              })
            ) : (
              // Single fill bar
              <div
                style={{
                  width: `${fillFraction * 100}%`,
                  height: "100%",
                  backgroundColor: color,
                  borderRadius,
                  transition:
                    animationStyle === "step"
                      ? "width 0.15s ease"
                      : undefined,
                }}
              />
            )}
          </div>

          {/* Segment labels below track */}
          {isSegmented && (
            <div
              style={{
                display: "flex",
                width: "100%",
                marginTop: 8,
              }}
            >
              {segments!.map((seg, i) => {
                const segDelay = 10 + i * 8;
                const labelOp = spring({
                  frame: frame - segDelay - 6,
                  fps,
                  config: { damping: 20 },
                });
                return (
                  <div
                    key={i}
                    style={{
                      width: `${(seg.value / 100) * 100}%`,
                      fontFamily,
                      fontWeight: 500,
                      fontSize: 18,
                      color: textColor,
                      textAlign: "center",
                      opacity: labelOp,
                    }}
                  >
                    {seg.label}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Percentage */}
        {showPercentage && !isSegmented && (
          <div
            style={{
              fontFamily,
              fontWeight: 800,
              fontSize: percentageFontSize,
              color,
              opacity: percentOpacity,
            }}
          >
            {displayedPercent}%
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
