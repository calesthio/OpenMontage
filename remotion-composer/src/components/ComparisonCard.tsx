import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

type ChangeDirection = "up" | "down" | "neutral";

interface ComparisonCardProps {
  leftLabel: string;
  rightLabel: string;
  leftValue: string;
  rightValue: string;
  leftColor?: string;
  rightColor?: string;
  title?: string;
  changeIndicator?: string;
  changeDirection?: ChangeDirection;
  backgroundColor?: string;
  cardBackgroundColor?: string;
  textColor?: string;
  fontFamily?: string;
  titleFontSize?: number;
  labelFontSize?: number;
  valueFontSize?: number;
}

export const ComparisonCard: React.FC<ComparisonCardProps> = ({
  leftLabel,
  rightLabel,
  leftValue,
  rightValue,
  leftColor = "#2563EB",
  rightColor = "#10B981",
  title,
  changeIndicator,
  changeDirection = "neutral",
  backgroundColor = "#FFFFFF",
  cardBackgroundColor = "#F3F4F6",
  textColor = "#1F2937",
  fontFamily = "Inter, system-ui, sans-serif",
  titleFontSize = 44,
  labelFontSize = 28,
  valueFontSize = 72,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  // Portrait (e.g. 1080x1920 shorts): stack before above after with a
  // horizontal divider, and rein in the value size so long phrases fit.
  const portrait = height > width;
  const effectiveValueFontSize = portrait
    ? Math.min(valueFontSize, 56)
    : valueFontSize;

  // Phase 1: Title + left side appears
  const titleOpacity = spring({
    frame,
    fps,
    config: { damping: 20 },
  });

  const leftOpacity = spring({
    frame: frame - 6,
    fps,
    config: { damping: 18 },
  });
  const leftSlide = spring({
    frame: frame - 6,
    fps,
    config: { damping: 14, stiffness: 90 },
    from: -40,
    to: 0,
  });
  const leftScale = spring({
    frame: frame - 6,
    fps,
    config: { damping: 12, stiffness: 100 },
    from: 0.9,
    to: 1,
  });

  // Phase 2: Divider draws in (vertical line)
  const dividerDraw = spring({
    frame: frame - 16,
    fps,
    config: { damping: 14, stiffness: 80 },
  });

  // Phase 3: Right side appears
  const rightOpacity = spring({
    frame: frame - 24,
    fps,
    config: { damping: 18 },
  });
  const rightSlide = spring({
    frame: frame - 24,
    fps,
    config: { damping: 14, stiffness: 90 },
    from: 40,
    to: 0,
  });
  const rightScale = spring({
    frame: frame - 24,
    fps,
    config: { damping: 12, stiffness: 100 },
    from: 0.9,
    to: 1,
  });

  // Phase 4: Change indicator
  const indicatorOpacity = spring({
    frame: frame - 32,
    fps,
    config: { damping: 15 },
  });
  const indicatorScale = spring({
    frame: frame - 32,
    fps,
    config: { damping: 10, stiffness: 130 },
    from: 0.6,
    to: 1,
  });

  // Arrow glyph based on direction
  const directionArrow =
    changeDirection === "up"
      ? "\u2191"
      : changeDirection === "down"
        ? "\u2193"
        : "\u2194";
  const directionColor =
    changeDirection === "up"
      ? "#10B981"
      : changeDirection === "down"
        ? "#EF4444"
        : "#9CA3AF";

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
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          width: "80%",
          maxWidth: 1540,
          gap: 32,
        }}
      >
        {/* Title */}
        {title && (
          <div
            style={{
              fontFamily,
              fontWeight: 700,
              fontSize: titleFontSize,
              color: textColor,
              textAlign: "center",
              opacity: titleOpacity,
              letterSpacing: "-0.02em",
            }}
          >
            {title}
          </div>
        )}

        {/* Comparison container */}
        <div
          style={{
            display: "flex",
            flexDirection: portrait ? "column" : "row",
            alignItems: "stretch",
            width: "100%",
            borderRadius: 16,
            backgroundColor: cardBackgroundColor,
            overflow: "hidden",
            boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
            minHeight: 280,
          }}
        >
          {/* Left side */}
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              padding: "48px 32px",
              opacity: leftOpacity,
              transform: `translate${portrait ? "Y" : "X"}(${leftSlide}px) scale(${leftScale})`,
              gap: 16,
            }}
          >
            {/* Left color accent bar */}
            <div
              style={{
                width: 48,
                height: 4,
                backgroundColor: leftColor,
                borderRadius: 2,
                marginBottom: 8,
              }}
            />
            <div
              style={{
                fontFamily,
                fontWeight: 600,
                fontSize: labelFontSize,
                color: textColor,
                opacity: 0.7,
                textTransform: "uppercase" as const,
                letterSpacing: "0.05em",
              }}
            >
              {leftLabel}
            </div>
            <div
              style={{
                fontFamily,
                fontWeight: 800,
                fontSize: effectiveValueFontSize,
                color: leftColor,
                lineHeight: 1.1,
              }}
            >
              {leftValue}
            </div>
          </div>

          {/* Center divider + change indicator */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              width: portrait ? "100%" : 80,
              height: portrait ? 64 : undefined,
              position: "relative",
            }}
          >
            {/* Divider line: vertical in landscape, horizontal in portrait */}
            <div
              style={
                portrait
                  ? {
                      height: 2,
                      width: `${dividerDraw * 100}%`,
                      backgroundColor: "#D1D5DB",
                      position: "absolute",
                      left: `${((1 - dividerDraw) / 2) * 100}%`,
                    }
                  : {
                      width: 2,
                      height: `${dividerDraw * 100}%`,
                      backgroundColor: "#D1D5DB",
                      position: "absolute",
                      top: `${((1 - dividerDraw) / 2) * 100}%`,
                    }
              }
            />

            {/* Change indicator badge */}
            {changeIndicator && (
              <div
                style={{
                  position: "relative",
                  zIndex: 1,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 4,
                  opacity: indicatorOpacity,
                  transform: `scale(${indicatorScale})`,
                }}
              >
                <div
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 24,
                    backgroundColor,
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    boxShadow: "0 1px 4px rgba(0,0,0,0.1)",
                  }}
                >
                  <span
                    style={{
                      fontFamily,
                      fontWeight: 700,
                      fontSize: 24,
                      color: directionColor,
                    }}
                  >
                    {directionArrow}
                  </span>
                </div>
                <div
                  style={{
                    fontFamily,
                    fontWeight: 700,
                    fontSize: 18,
                    color: directionColor,
                    whiteSpace: "nowrap" as const,
                  }}
                >
                  {changeIndicator}
                </div>
              </div>
            )}
          </div>

          {/* Right side */}
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              padding: "48px 32px",
              opacity: rightOpacity,
              transform: `translate${portrait ? "Y" : "X"}(${rightSlide}px) scale(${rightScale})`,
              gap: 16,
            }}
          >
            {/* Right color accent bar */}
            <div
              style={{
                width: 48,
                height: 4,
                backgroundColor: rightColor,
                borderRadius: 2,
                marginBottom: 8,
              }}
            />
            <div
              style={{
                fontFamily,
                fontWeight: 600,
                fontSize: labelFontSize,
                color: textColor,
                opacity: 0.7,
                textTransform: "uppercase" as const,
                letterSpacing: "0.05em",
              }}
            >
              {rightLabel}
            </div>
            <div
              style={{
                fontFamily,
                fontWeight: 800,
                fontSize: effectiveValueFontSize,
                color: rightColor,
                lineHeight: 1.1,
              }}
            >
              {rightValue}
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
