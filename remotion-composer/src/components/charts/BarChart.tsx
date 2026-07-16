import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { withCjkFallback } from "../../fonts";

interface BarDatum {
  label: string;
  value: number;
}

type BarAnimationStyle = "grow-up" | "slide-in" | "pop";

interface BarChartProps {
  data: BarDatum[];
  title?: string;
  colors?: string[];
  fontFamily?: string;
  textColor?: string;
  backgroundColor?: string;
  gridColor?: string;
  showGrid?: boolean;
  showValues?: boolean;
  animationStyle?: BarAnimationStyle;
  barGap?: number;
}

export const BarChart: React.FC<BarChartProps> = ({
  data,
  title,
  colors = ["#2563EB", "#F59E0B", "#10B981", "#EC4899", "#06B6D4", "#8B5CF6"],
  fontFamily = withCjkFallback("Inter, system-ui, sans-serif"),
  textColor = "#1F2937",
  backgroundColor = "#FFFFFF",
  gridColor = "#E5E7EB",
  showGrid = true,
  showValues = true,
  animationStyle = "grow-up",
  barGap = 12,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width: W, height: H } = useVideoConfig();

  const maxValue = Math.max(...data.map((d) => d.value), 1);

  // Layout derived from the actual composition size (audit 2026-07-16,
  // Wave 3 item 14) — the old hardcoded 1920×1080 constants letterboxed or
  // clipped in the vertical 9:16 compositions real customer projects use.
  const chartLeft = Math.round(W * 0.073);
  const chartRight = W - Math.round(W * 0.073);
  const chartTop = title ? Math.round(H * 0.148) : Math.round(H * 0.074);
  const chartBottom = H - Math.round(H * 0.148);
  const chartWidth = chartRight - chartLeft;
  const chartHeight = chartBottom - chartTop;

  // Type scale follows the smaller dimension so vertical 9:16 keeps the
  // same optical size (item 19: the old 20-22px labels were illegibly
  // small on a 1080p+ frame).
  const fs = (n: number) => Math.round((n * Math.min(W, H)) / 1080);

  const barCount = data.length;
  const totalGap = barGap * (barCount + 1);
  const barWidth = Math.min(
    (chartWidth - totalGap) / barCount,
    Math.round(W * 0.0625)
  );
  const actualTotalWidth = barCount * barWidth + (barCount + 1) * barGap;
  const offsetX = chartLeft + (chartWidth - actualTotalWidth) / 2;

  // Grid lines
  const gridLineCount = 5;
  const gridLines = Array.from({ length: gridLineCount + 1 }, (_, i) => {
    const value = (maxValue / gridLineCount) * i;
    const y = chartBottom - (i / gridLineCount) * chartHeight;
    return { value, y };
  });

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
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: "100%" }}
      >
        {/* Subtle vertical sheen per bar color — flat single-color rects
            read as "spreadsheet", the gradient reads as "designed". */}
        <defs>
          {colors.map((c, i) => (
            <linearGradient key={i} id={`bar-grad-${i}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={c} stopOpacity={1} />
              <stop offset="100%" stopColor={c} stopOpacity={0.78} />
            </linearGradient>
          ))}
        </defs>

        {/* Title */}
        {title && (
          <text
            x={W / 2}
            y={Math.round(H * 0.074)}
            textAnchor="middle"
            fill={textColor}
            fontFamily={fontFamily}
            fontWeight={700}
            fontSize={fs(48)}
            opacity={spring({ frame, fps, config: { damping: 20 } })}
          >
            {title}
          </text>
        )}

        {/* Grid lines */}
        {showGrid &&
          gridLines.map((line, i) => {
            const gridOpacity = interpolate(
              frame,
              [0, 10],
              [0, 0.6],
              { extrapolateRight: "clamp" }
            );
            return (
              <g key={`grid-${i}`}>
                <line
                  x1={chartLeft}
                  y1={line.y}
                  x2={chartRight}
                  y2={line.y}
                  stroke={gridColor}
                  strokeWidth={1}
                  opacity={gridOpacity}
                />
                <text
                  x={chartLeft - 12}
                  y={line.y + 5}
                  textAnchor="end"
                  fill={textColor}
                  fontFamily={fontFamily}
                  fontWeight={400}
                  fontSize={fs(28)}
                  opacity={gridOpacity}
                >
                  {formatNumber(line.value)}
                </text>
              </g>
            );
          })}

        {/* Axis lines */}
        <line
          x1={chartLeft}
          y1={chartTop}
          x2={chartLeft}
          y2={chartBottom}
          stroke={gridColor}
          strokeWidth={2}
          opacity={interpolate(frame, [0, 8], [0, 1], {
            extrapolateRight: "clamp",
          })}
        />
        <line
          x1={chartLeft}
          y1={chartBottom}
          x2={chartRight}
          y2={chartBottom}
          stroke={gridColor}
          strokeWidth={2}
          opacity={interpolate(frame, [0, 8], [0, 1], {
            extrapolateRight: "clamp",
          })}
        />

        {/* Bars */}
        {data.map((datum, i) => {
          const color = colors[i % colors.length];
          const barX = offsetX + barGap + i * (barWidth + barGap);
          const barHeightFull = (datum.value / maxValue) * chartHeight;
          const staggerDelay = i * 4;

          let barProgress: number;
          let barOpacity: number;

          if (animationStyle === "grow-up") {
            barProgress = spring({
              frame: frame - staggerDelay,
              fps,
              config: { damping: 14, stiffness: 80 },
            });
            barOpacity = interpolate(
              frame,
              [staggerDelay, staggerDelay + 6],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
          } else if (animationStyle === "slide-in") {
            barProgress = interpolate(
              frame,
              [staggerDelay + 5, staggerDelay + 25],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
            barOpacity = interpolate(
              frame,
              [staggerDelay + 5, staggerDelay + 12],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
          } else {
            // pop
            const s = spring({
              frame: frame - staggerDelay,
              fps,
              config: { damping: 8, stiffness: 150, mass: 0.6 },
            });
            barProgress = s;
            barOpacity = interpolate(
              frame,
              [staggerDelay, staggerDelay + 3],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
          }

          const animatedHeight = barHeightFull * barProgress;
          const barY = chartBottom - animatedHeight;

          // Fade out near end
          const fadeOut = interpolate(
            frame,
            [durationInFrames - 15, durationInFrames],
            [1, 0],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );

          return (
            <g key={datum.label} opacity={fadeOut}>
              {/* Bar */}
              <rect
                x={barX}
                y={barY}
                width={barWidth}
                height={Math.max(animatedHeight, 0)}
                fill={`url(#bar-grad-${i % colors.length})`}
                rx={4}
                opacity={barOpacity}
              />

              {/* Value label — counts up with the bar growth (item 19),
                  landing on the exact formatted value. */}
              {showValues && (
                <text
                  x={barX + barWidth / 2}
                  y={barY - fs(14)}
                  textAnchor="middle"
                  fill={textColor}
                  fontFamily={fontFamily}
                  fontWeight={600}
                  fontSize={fs(30)}
                  opacity={interpolate(
                    barProgress,
                    [0.4, 1],
                    [0, 1],
                    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
                  )}
                >
                  {formatNumber(datum.value * Math.min(1, Math.max(0, barProgress)))}
                </text>
              )}

              {/* Label */}
              <text
                x={barX + barWidth / 2}
                y={chartBottom + fs(44)}
                textAnchor="middle"
                fill={textColor}
                fontFamily={fontFamily}
                fontWeight={500}
                fontSize={fs(28)}
                opacity={barOpacity}
              >
                {datum.label}
              </text>
            </g>
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(1);
}
