import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { withCjkFallback } from "../../fonts";

interface PieDatum {
  label: string;
  value: number;
  color?: string;
}

type PieAnimationStyle = "spin" | "expand" | "sequential";

interface PieChartProps {
  data: PieDatum[];
  title?: string;
  colors?: string[];
  fontFamily?: string;
  textColor?: string;
  backgroundColor?: string;
  donut?: boolean;
  centerLabel?: string;
  centerValue?: string;
  showLegend?: boolean;
  animationStyle?: PieAnimationStyle;
}

export const PieChart: React.FC<PieChartProps> = ({
  data,
  title,
  colors = ["#2563EB", "#F59E0B", "#10B981", "#EC4899", "#06B6D4", "#8B5CF6"],
  fontFamily = withCjkFallback("Inter, system-ui, sans-serif"),
  textColor = "#1F2937",
  backgroundColor = "#FFFFFF",
  donut = false,
  centerLabel,
  centerValue,
  showLegend = true,
  animationStyle = "expand",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const total = data.reduce((sum, d) => sum + d.value, 0) || 1;

  // Layout
  const cx = showLegend ? 760 : 960;
  const cy = title ? 540 : 500;
  const outerRadius = 300;
  const innerRadius = donut ? outerRadius * 0.55 : 0;

  // Build slice angles
  const slices: {
    datum: PieDatum;
    color: string;
    startAngle: number;
    endAngle: number;
    percentage: number;
  }[] = [];
  let cumAngle = -Math.PI / 2; // start from top
  data.forEach((datum, i) => {
    const angle = (datum.value / total) * 2 * Math.PI;
    slices.push({
      datum,
      color: datum.color || colors[i % colors.length],
      startAngle: cumAngle,
      endAngle: cumAngle + angle,
      percentage: (datum.value / total) * 100,
    });
    cumAngle += angle;
  });

  // Animation progress
  const globalProgress = spring({
    frame: frame - 5,
    fps,
    config: { damping: 18, stiffness: 50 },
  });

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
        padding: 40,
      }}
    >
      <svg
        viewBox="0 0 1920 1080"
        style={{ width: "100%", height: "100%" }}
      >
        {/* Title */}
        {title && (
          <text
            x={960}
            y={80}
            textAnchor="middle"
            fill={textColor}
            fontFamily={fontFamily}
            fontWeight={700}
            fontSize={48}
            opacity={spring({ frame, fps, config: { damping: 20 } })}
          >
            {title}
          </text>
        )}

        {/* Pie/donut slices */}
        <g opacity={fadeOut}>
          {slices.map((slice, i) => {
            let sliceProgress: number;
            let sliceOpacity: number;

            if (animationStyle === "spin") {
              // All slices animate together by sweeping the full circle
              sliceProgress = globalProgress;
              sliceOpacity = interpolate(
                frame,
                [3, 10],
                [0, 1],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
              );
            } else if (animationStyle === "expand") {
              // Radial expand from center
              sliceProgress = 1; // full angles immediately
              sliceOpacity = globalProgress;
            } else {
              // sequential — each slice appears one after another
              const staggerDelay = i * 6;
              sliceProgress = spring({
                frame: frame - staggerDelay - 5,
                fps,
                config: { damping: 16, stiffness: 60 },
              });
              sliceOpacity = interpolate(
                frame,
                [staggerDelay + 3, staggerDelay + 8],
                [0, 1],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
              );
            }

            // For "spin", we progressively reveal slices by clipping the end angle
            const totalSweep = slice.endAngle - (-Math.PI / 2);
            const maxSweep = 2 * Math.PI;
            let effectiveStartAngle = slice.startAngle;
            let effectiveEndAngle = slice.endAngle;

            if (animationStyle === "spin") {
              const currentMaxAngle = -Math.PI / 2 + maxSweep * sliceProgress;
              if (slice.startAngle >= currentMaxAngle) {
                // slice not visible yet
                return null;
              }
              effectiveEndAngle = Math.min(slice.endAngle, currentMaxAngle);
            }

            if (animationStyle === "sequential") {
              const sliceAngleSpan = slice.endAngle - slice.startAngle;
              effectiveEndAngle =
                slice.startAngle + sliceAngleSpan * sliceProgress;
            }

            // For "expand", scale the radius
            const currentOuterRadius =
              animationStyle === "expand"
                ? outerRadius * globalProgress
                : outerRadius;
            const currentInnerRadius =
              animationStyle === "expand"
                ? innerRadius * globalProgress
                : innerRadius;

            const path = describeArc(
              cx,
              cy,
              currentOuterRadius,
              currentInnerRadius,
              effectiveStartAngle,
              effectiveEndAngle
            );

            return (
              <path
                key={slice.datum.label}
                d={path}
                fill={slice.color}
                opacity={sliceOpacity}
                stroke={backgroundColor}
                strokeWidth={2}
              />
            );
          })}

          {/* Donut center */}
          {donut && (centerLabel || centerValue) && (
            <g
              opacity={interpolate(
                globalProgress,
                [0.5, 1],
                [0, 1],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
              )}
            >
              {centerValue && (
                <text
                  x={cx}
                  y={centerLabel ? cy - 10 : cy + 10}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill={textColor}
                  fontFamily={fontFamily}
                  fontWeight={800}
                  fontSize={56}
                >
                  {centerValue}
                </text>
              )}
              {centerLabel && (
                <text
                  x={cx}
                  y={centerValue ? cy + 36 : cy + 10}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill={textColor}
                  fontFamily={fontFamily}
                  fontWeight={400}
                  fontSize={24}
                  opacity={0.7}
                >
                  {centerLabel}
                </text>
              )}
            </g>
          )}
        </g>

        {/* Legend */}
        {showLegend && (
          <g opacity={fadeOut}>
            {slices.map((slice, i) => {
              const legendY = cy - (slices.length * 44) / 2 + i * 44;
              const legendX = showLegend ? 1200 : cx + outerRadius + 80;
              const legendOpacity = spring({
                frame: frame - 15 - i * 3,
                fps,
                config: { damping: 20 },
              });
              return (
                <g key={`legend-${i}`} opacity={legendOpacity}>
                  <rect
                    x={legendX}
                    y={legendY - 8}
                    width={20}
                    height={20}
                    rx={4}
                    fill={slice.color}
                  />
                  <text
                    x={legendX + 32}
                    y={legendY + 6}
                    fill={textColor}
                    fontFamily={fontFamily}
                    fontSize={22}
                    fontWeight={500}
                  >
                    {slice.datum.label}
                  </text>
                  <text
                    x={legendX + 32}
                    y={legendY + 6}
                    fill={textColor}
                    fontFamily={fontFamily}
                    fontSize={22}
                    fontWeight={400}
                    opacity={0.6}
                    textAnchor="end"
                    dx={280}
                  >
                    {slice.percentage.toFixed(1)}%
                  </text>
                </g>
              );
            })}
          </g>
        )}
      </svg>
    </AbsoluteFill>
  );
};

/**
 * Build an SVG arc path for a pie/donut slice.
 */
function describeArc(
  cx: number,
  cy: number,
  outerR: number,
  innerR: number,
  startAngle: number,
  endAngle: number
): string {
  const outerStart = polarToCartesian(cx, cy, outerR, startAngle);
  const outerEnd = polarToCartesian(cx, cy, outerR, endAngle);
  const largeArc = endAngle - startAngle > Math.PI ? 1 : 0;

  if (innerR <= 0) {
    // Full pie slice
    return [
      `M ${cx} ${cy}`,
      `L ${outerStart.x} ${outerStart.y}`,
      `A ${outerR} ${outerR} 0 ${largeArc} 1 ${outerEnd.x} ${outerEnd.y}`,
      "Z",
    ].join(" ");
  }

  // Donut slice
  const innerStart = polarToCartesian(cx, cy, innerR, startAngle);
  const innerEnd = polarToCartesian(cx, cy, innerR, endAngle);

  return [
    `M ${outerStart.x} ${outerStart.y}`,
    `A ${outerR} ${outerR} 0 ${largeArc} 1 ${outerEnd.x} ${outerEnd.y}`,
    `L ${innerEnd.x} ${innerEnd.y}`,
    `A ${innerR} ${innerR} 0 ${largeArc} 0 ${innerStart.x} ${innerStart.y}`,
    "Z",
  ].join(" ");
}

function polarToCartesian(
  cx: number,
  cy: number,
  r: number,
  angle: number
): { x: number; y: number } {
  return {
    x: cx + r * Math.cos(angle),
    y: cy + r * Math.sin(angle),
  };
}
