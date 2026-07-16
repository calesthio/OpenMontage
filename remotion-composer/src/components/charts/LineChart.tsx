import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { withCjkFallback } from "../../fonts";

interface DataPoint {
  x: number;
  y: number;
}

interface Series {
  label: string;
  data: DataPoint[];
  color?: string;
}

type LineAnimationStyle = "draw" | "fade-in";

interface LineChartProps {
  series: Series[];
  title?: string;
  colors?: string[];
  fontFamily?: string;
  textColor?: string;
  backgroundColor?: string;
  gridColor?: string;
  showGrid?: boolean;
  showMarkers?: boolean;
  showLegend?: boolean;
  xLabel?: string;
  yLabel?: string;
  animationStyle?: LineAnimationStyle;
  strokeWidth?: number;
}

export const LineChart: React.FC<LineChartProps> = ({
  series,
  title,
  colors = ["#2563EB", "#F59E0B", "#10B981", "#EC4899", "#06B6D4", "#8B5CF6"],
  fontFamily = withCjkFallback("Inter, system-ui, sans-serif"),
  textColor = "#1F2937",
  backgroundColor = "#FFFFFF",
  gridColor = "#E5E7EB",
  showGrid = true,
  showMarkers = true,
  showLegend = true,
  xLabel,
  yLabel,
  animationStyle = "draw",
  strokeWidth = 3,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width: W, height: H } = useVideoConfig();

  // Layout derived from the composition size (Wave 3 item 14 — hardcoded
  // 1920×1080 constants broke vertical 9:16); type scale follows the
  // smaller dimension (item 19 — 18px axis labels were illegible).
  const fs = (n: number) => Math.round((n * Math.min(W, H)) / 1080);
  const chartLeft = Math.round(W * 0.083);
  const chartRight = W - Math.round(W * 0.083);
  const chartTop = title ? Math.round(H * 0.148) : Math.round(H * 0.093);
  const chartBottom = showLegend ? H - Math.round(H * 0.185) : H - Math.round(H * 0.13);
  const chartWidth = chartRight - chartLeft;
  const chartHeight = chartBottom - chartTop;

  // Compute data bounds across all series
  const allPoints = series.flatMap((s) => s.data);
  const xMin = Math.min(...allPoints.map((p) => p.x));
  const xMax = Math.max(...allPoints.map((p) => p.x));
  const yMin = 0;
  const yMax = Math.max(...allPoints.map((p) => p.y)) * 1.1; // 10% headroom

  const toSvgX = (x: number) =>
    chartLeft + ((x - xMin) / (xMax - xMin || 1)) * chartWidth;
  const toSvgY = (y: number) =>
    chartBottom - ((y - yMin) / (yMax - yMin || 1)) * chartHeight;

  // Grid
  const gridLineCountY = 5;
  const gridLinesY = Array.from({ length: gridLineCountY + 1 }, (_, i) => {
    const value = (yMax / gridLineCountY) * i;
    const y = toSvgY(value);
    return { value, y };
  });

  const gridLineCountX = Math.min(allPoints.length - 1, 6);
  const gridLinesX = Array.from({ length: gridLineCountX + 1 }, (_, i) => {
    const value = xMin + ((xMax - xMin) / gridLineCountX) * i;
    const x = toSvgX(value);
    return { value, x };
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
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: "100%" }}
      >
        {/* Area fill gradients — one per series color (item 19: the naked
            polyline read as "engineering plot"; line + soft area is the
            Flourish-grade baseline). */}
        <defs>
          {series.map((s, i) => {
            const c = s.color || colors[i % colors.length];
            return (
              <linearGradient key={i} id={`line-area-${i}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={c} stopOpacity={0.28} />
                <stop offset="100%" stopColor={c} stopOpacity={0.02} />
              </linearGradient>
            );
          })}
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

        {/* Grid */}
        {showGrid && (
          <g
            opacity={interpolate(frame, [0, 10], [0, 0.5], {
              extrapolateRight: "clamp",
            })}
          >
            {/* Horizontal grid */}
            {gridLinesY.map((line, i) => (
              <g key={`gy-${i}`}>
                <line
                  x1={chartLeft}
                  y1={line.y}
                  x2={chartRight}
                  y2={line.y}
                  stroke={gridColor}
                  strokeWidth={1}
                />
                <text
                  x={chartLeft - 14}
                  y={line.y + 6}
                  textAnchor="end"
                  fill={textColor}
                  fontFamily={fontFamily}
                  fontSize={fs(26)}
                  fontWeight={400}
                >
                  {formatNumber(line.value)}
                </text>
              </g>
            ))}
            {/* Vertical grid */}
            {gridLinesX.map((line, i) => (
              <g key={`gx-${i}`}>
                <line
                  x1={line.x}
                  y1={chartTop}
                  x2={line.x}
                  y2={chartBottom}
                  stroke={gridColor}
                  strokeWidth={1}
                />
                <text
                  x={line.x}
                  y={chartBottom + fs(38)}
                  textAnchor="middle"
                  fill={textColor}
                  fontFamily={fontFamily}
                  fontSize={fs(26)}
                  fontWeight={400}
                >
                  {formatNumber(line.value)}
                </text>
              </g>
            ))}
          </g>
        )}

        {/* Axes */}
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

        {/* Axis labels */}
        {xLabel && (
          <text
            x={chartLeft + chartWidth / 2}
            y={chartBottom + fs(74)}
            textAnchor="middle"
            fill={textColor}
            fontFamily={fontFamily}
            fontSize={fs(28)}
            fontWeight={500}
            opacity={interpolate(frame, [5, 15], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })}
          >
            {xLabel}
          </text>
        )}
        {yLabel && (
          <text
            x={fs(44)}
            y={chartTop + chartHeight / 2}
            textAnchor="middle"
            fill={textColor}
            fontFamily={fontFamily}
            fontSize={fs(28)}
            fontWeight={500}
            transform={`rotate(-90, ${fs(44)}, ${chartTop + chartHeight / 2})`}
            opacity={interpolate(frame, [5, 15], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })}
          >
            {yLabel}
          </text>
        )}

        {/* Series lines */}
        {series.map((s, seriesIdx) => {
          const color = s.color || colors[seriesIdx % colors.length];
          const sorted = [...s.data].sort((a, b) => a.x - b.x);
          if (sorted.length < 2) return null;

          const svgPoints = sorted.map((p) => ({ x: toSvgX(p.x), y: toSvgY(p.y) }));
          // Monotone cubic spline — smooth without overshooting the data
          // (a plain Catmull-Rom bulges past extremes, which misreads in a
          // data chart; Fritsch–Carlson stays inside the data envelope).
          const pathD = monotonePath(svgPoints);
          const areaD = `${pathD} L ${svgPoints[svgPoints.length - 1].x} ${chartBottom} L ${svgPoints[0].x} ${chartBottom} Z`;

          // Approximate path length for dash animation (chord length ×1.05
          // headroom for spline curvature).
          let pathLength = 0;
          for (let i = 1; i < svgPoints.length; i++) {
            const dx = svgPoints[i].x - svgPoints[i - 1].x;
            const dy = svgPoints[i].y - svgPoints[i - 1].y;
            pathLength += Math.sqrt(dx * dx + dy * dy);
          }
          pathLength *= 1.05;

          const staggerDelay = seriesIdx * 8;

          let drawProgress: number;
          let lineOpacity: number;

          if (animationStyle === "draw") {
            drawProgress = spring({
              frame: frame - staggerDelay - 8,
              fps,
              config: { damping: 20, stiffness: 40 },
            });
            lineOpacity = interpolate(
              frame,
              [staggerDelay + 5, staggerDelay + 10],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
          } else {
            // fade-in
            drawProgress = 1;
            lineOpacity = spring({
              frame: frame - staggerDelay - 5,
              fps,
              config: { damping: 20 },
            });
          }

          const dashOffset = pathLength * (1 - drawProgress);

          return (
            <g key={s.label} opacity={fadeOut}>
              {/* Area fill under the line — revealed with the draw */}
              <path
                d={areaD}
                fill={`url(#line-area-${seriesIdx})`}
                stroke="none"
                opacity={lineOpacity * drawProgress}
              />
              {/* Line */}
              <path
                d={pathD}
                fill="none"
                stroke={color}
                strokeWidth={strokeWidth}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={pathLength}
                strokeDashoffset={dashOffset}
                opacity={lineOpacity}
              />

              {/* Markers */}
              {showMarkers &&
                sorted.map((p, pIdx) => {
                  const markerProgress = interpolate(
                    drawProgress,
                    [pIdx / sorted.length, Math.min((pIdx + 1) / sorted.length, 1)],
                    [0, 1],
                    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
                  );
                  return (
                    <circle
                      key={`${s.label}-p-${pIdx}`}
                      cx={toSvgX(p.x)}
                      cy={toSvgY(p.y)}
                      r={fs(6)}
                      fill={backgroundColor}
                      stroke={color}
                      strokeWidth={2.5}
                      opacity={markerProgress * lineOpacity}
                    />
                  );
                })}
            </g>
          );
        })}

        {/* Legend */}
        {showLegend && series.length > 1 && (
          <g
            opacity={interpolate(frame, [15, 25], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })}
          >
            {series.map((s, i) => {
              const color = s.color || colors[i % colors.length];
              const legendX = W / 2 - (series.length * fs(200)) / 2 + i * fs(200);
              return (
                <g key={`legend-${i}`}>
                  <rect
                    x={legendX}
                    y={chartBottom + fs(90)}
                    width={24}
                    height={4}
                    rx={2}
                    fill={color}
                  />
                  <text
                    x={legendX + fs(32)}
                    y={chartBottom + fs(96)}
                    fill={textColor}
                    fontFamily={fontFamily}
                    fontSize={fs(26)}
                    fontWeight={500}
                  >
                    {s.label}
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

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(1);
}

/** Fritsch–Carlson monotone cubic interpolation → SVG cubic-bezier path.
 *  Smooth between points, never overshooting the data envelope. */
function monotonePath(pts: { x: number; y: number }[]): string {
  const n = pts.length;
  if (n < 2) return "";
  const dx: number[] = [];
  const slope: number[] = [];
  for (let i = 0; i < n - 1; i++) {
    const h = pts[i + 1].x - pts[i].x;
    dx.push(h);
    slope.push((pts[i + 1].y - pts[i].y) / (h || 1e-9));
  }
  const tangent: number[] = [slope[0]];
  for (let i = 1; i < n - 1; i++) {
    tangent.push(slope[i - 1] * slope[i] <= 0 ? 0 : (slope[i - 1] + slope[i]) / 2);
  }
  tangent.push(slope[n - 2]);
  for (let i = 0; i < n - 1; i++) {
    if (slope[i] === 0) {
      tangent[i] = 0;
      tangent[i + 1] = 0;
      continue;
    }
    const a = tangent[i] / slope[i];
    const b = tangent[i + 1] / slope[i];
    const s = a * a + b * b;
    if (s > 9) {
      const tau = 3 / Math.sqrt(s);
      tangent[i] = tau * a * slope[i];
      tangent[i + 1] = tau * b * slope[i];
    }
  }
  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 0; i < n - 1; i++) {
    const h = dx[i];
    d +=
      ` C ${pts[i].x + h / 3} ${pts[i].y + (tangent[i] * h) / 3}` +
      ` ${pts[i + 1].x - h / 3} ${pts[i + 1].y - (tangent[i + 1] * h) / 3}` +
      ` ${pts[i + 1].x} ${pts[i + 1].y}`;
  }
  return d;
}
