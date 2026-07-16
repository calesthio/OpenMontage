import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { withCjkFallback } from "../../fonts";

interface Metric {
  label: string;
  value: number;
  prefix?: string;
  suffix?: string;
  change?: number; // percentage change, positive = up, negative = down
  icon?: string; // emoji or text glyph
}

type KPIAnimationStyle = "count-up" | "pop" | "cascade";

interface KPIGridProps {
  metrics: Metric[];
  title?: string;
  columns?: 2 | 3 | 4;
  colors?: string[];
  fontFamily?: string;
  textColor?: string;
  backgroundColor?: string;
  cardBackgroundColor?: string;
  positiveColor?: string;
  negativeColor?: string;
  animationStyle?: KPIAnimationStyle;
}

export const KPIGrid: React.FC<KPIGridProps> = ({
  metrics,
  title,
  columns = 3,
  colors = ["#2563EB", "#F59E0B", "#10B981", "#EC4899"],
  fontFamily = withCjkFallback("Inter, system-ui, sans-serif"),
  textColor = "#1F2937",
  backgroundColor = "#FFFFFF",
  cardBackgroundColor = "#F9FAFB",
  positiveColor = "#10B981",
  negativeColor = "#EF4444",
  animationStyle = "count-up",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width: W, height: H } = useVideoConfig();
  // Responsive layout (Wave 3 item 14).
  const fs = (n: number) => Math.round((n * Math.min(W, H)) / 1080);

  const cols = Math.min(columns, metrics.length);
  const rows = Math.ceil(metrics.length / cols);

  const gridPadding = Math.round(W * 0.052);
  const cardGap = fs(28);
  const titleHeight = title ? Math.round(H * 0.111) : 0;
  const gridTop = Math.round(H * 0.074) + titleHeight;
  const gridWidth = W - gridPadding * 2;
  const gridHeight = H - gridTop - Math.round(H * 0.074);
  const cardWidth = (gridWidth - cardGap * (cols - 1)) / cols;
  const cardHeight = Math.min(
    (gridHeight - cardGap * (rows - 1)) / rows,
    fs(320)
  );

  // Center grid vertically
  const totalGridHeight = rows * cardHeight + (rows - 1) * cardGap;
  const gridTopOffset = gridTop + (gridHeight - totalGridHeight) / 2;

  // Fade out near end
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 15, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill
      style={{
        background: backgroundColor,
        justifyContent: "flex-start",
        alignItems: "center",
        fontFamily,
      }}
    >
      {/* Title */}
      {title && (
        <div
          style={{
            position: "absolute",
            top: 60,
            left: 0,
            right: 0,
            textAlign: "center",
            fontSize: 48,
            fontWeight: 700,
            color: textColor,
            fontFamily,
            opacity:
              spring({ frame, fps, config: { damping: 20 } }) * fadeOut,
          }}
        >
          {title}
        </div>
      )}

      {/* Cards */}
      {metrics.map((metric, idx) => {
        const col = idx % cols;
        const row = Math.floor(idx / cols);
        const left = gridPadding + col * (cardWidth + cardGap);
        const top = gridTopOffset + row * (cardHeight + cardGap);
        const accentColor = colors[idx % colors.length];

        const staggerDelay =
          animationStyle === "cascade" ? idx * 5 : 0;

        // Card entrance
        let cardScale: number;
        let cardOpacity: number;

        if (animationStyle === "pop") {
          cardScale = spring({
            frame: frame - idx * 4,
            fps,
            config: { damping: 10, stiffness: 150, mass: 0.5 },
            from: 0.7,
            to: 1,
          });
          cardOpacity = interpolate(
            frame,
            [idx * 4, idx * 4 + 5],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
        } else if (animationStyle === "cascade") {
          cardScale = 1;
          const slideY = interpolate(
            frame,
            [staggerDelay, staggerDelay + 15],
            [30, 0],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
          cardOpacity = interpolate(
            frame,
            [staggerDelay, staggerDelay + 12],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
          // We'll use slideY via transform below
          return (
            <div
              key={metric.label}
              style={{
                position: "absolute",
                left,
                top,
                width: cardWidth,
                height: cardHeight,
                backgroundColor: cardBackgroundColor,
                borderRadius: 12,
                borderLeft: `4px solid ${accentColor}`,
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                alignItems: "center",
                padding: 24,
                opacity: cardOpacity * fadeOut,
                transform: `translateY(${slideY}px)`,
                boxShadow: "0 2px 12px rgba(0,0,0,0.06)",
              }}
            >
              <KPICardContent
                metric={metric}
                accentColor={accentColor}
                textColor={textColor}
                fontFamily={fontFamily}
                positiveColor={positiveColor}
                negativeColor={negativeColor}
                frame={frame}
                fps={fps}
                staggerDelay={staggerDelay}
                animationStyle={animationStyle}
              />
            </div>
          );
        } else {
          // count-up — no special card animation
          cardScale = 1;
          cardOpacity = spring({
            frame: frame - idx * 3,
            fps,
            config: { damping: 20 },
          });
        }

        return (
          <div
            key={metric.label}
            style={{
              position: "absolute",
              left,
              top,
              width: cardWidth,
              height: cardHeight,
              backgroundColor: cardBackgroundColor,
              borderRadius: 12,
              borderLeft: `4px solid ${accentColor}`,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              padding: 24,
              opacity: cardOpacity * fadeOut,
              transform: `scale(${cardScale})`,
              boxShadow: "0 2px 12px rgba(0,0,0,0.06)",
            }}
          >
            <KPICardContent
              metric={metric}
              accentColor={accentColor}
              textColor={textColor}
              fontFamily={fontFamily}
              positiveColor={positiveColor}
              negativeColor={negativeColor}
              frame={frame}
              fps={fps}
              staggerDelay={idx * 3}
              animationStyle={animationStyle}
            />
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

interface KPICardContentProps {
  metric: Metric;
  accentColor: string;
  textColor: string;
  fontFamily: string;
  positiveColor: string;
  negativeColor: string;
  frame: number;
  fps: number;
  staggerDelay: number;
  animationStyle: KPIAnimationStyle;
}

const KPICardContent: React.FC<KPICardContentProps> = ({
  metric,
  accentColor,
  textColor,
  fontFamily,
  positiveColor,
  negativeColor,
  frame,
  fps,
  staggerDelay,
  animationStyle,
}) => {
  // Count-up animation
  const countProgress =
    animationStyle === "count-up"
      ? spring({
          frame: frame - staggerDelay - 5,
          fps,
          config: { damping: 22, stiffness: 40 },
        })
      : spring({
          frame: frame - staggerDelay - 3,
          fps,
          config: { damping: 18, stiffness: 60 },
        });

  const displayValue = Math.round(metric.value * countProgress);
  const formattedValue = formatDisplayValue(displayValue, metric.value);

  // Change indicator animation
  const changeOpacity = interpolate(
    frame,
    [staggerDelay + 18, staggerDelay + 25],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <>
      {/* Icon */}
      {metric.icon && (
        <div
          style={{
            fontSize: 36,
            marginBottom: 8,
          }}
        >
          {metric.icon}
        </div>
      )}

      {/* Value */}
      <div
        style={{
          fontSize: 56,
          fontWeight: 800,
          color: accentColor,
          fontFamily,
          lineHeight: 1.1,
        }}
      >
        {metric.prefix || ""}
        {formattedValue}
        {metric.suffix || ""}
      </div>

      {/* Label */}
      <div
        style={{
          fontSize: 22,
          fontWeight: 500,
          color: textColor,
          fontFamily,
          marginTop: 8,
          opacity: 0.8,
        }}
      >
        {metric.label}
      </div>

      {/* Change indicator */}
      {metric.change !== undefined && metric.change !== 0 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            marginTop: 10,
            fontSize: 20,
            fontWeight: 600,
            fontFamily,
            color: metric.change > 0 ? positiveColor : negativeColor,
            opacity: changeOpacity,
          }}
        >
          <span style={{ fontSize: 18 }}>
            {metric.change > 0 ? "\u25B2" : "\u25BC"}
          </span>
          {Math.abs(metric.change).toFixed(1)}%
        </div>
      )}
    </>
  );
};

/**
 * Format the animated counter value to match the scale of the target value.
 */
function formatDisplayValue(current: number, target: number): string {
  if (target >= 1_000_000) {
    return `${(current / 1_000_000).toFixed(1)}M`;
  }
  if (target >= 1_000) {
    return `${(current / 1_000).toFixed(1)}K`;
  }
  return String(current);
}
