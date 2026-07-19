import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { evolvePath } from "@remotion/paths";

export interface DrawPathItem {
  /** SVG path data (the `d` attribute). */
  d: string;
  /** Stroke color for this path. Falls back to the scene `color`. */
  color?: string;
  /** Stroke width for this path. Falls back to the scene `strokeWidth`. */
  strokeWidth?: number;
  /** If set, the shape fills with this color after it finishes drawing. */
  fill?: string;
}

export interface DrawPathSceneProps {
  /** One or more paths to draw, in order. */
  paths: DrawPathItem[];
  /** SVG coordinate space the paths were authored in. Default "0 0 1920 1080". */
  viewBox?: string;
  /** Default stroke color when a path doesn't set its own. Default "#F59E0B". */
  color?: string;
  /** Default stroke width. Default 8. */
  strokeWidth?: number;
  /** Scene background. Default "transparent" so it can overlay a reel. */
  backgroundColor?: string;
  /** Frames it takes each path to draw itself. Default 40. */
  drawDurationInFrames?: number;
  /** Frames between the start of one path and the next. Default 12. */
  staggerFrames?: number;
  /** Frames over which a path's `fill` fades in once drawn. Default 12. */
  fillFadeInFrames?: number;
}

export const DrawPathScene: React.FC<DrawPathSceneProps> = ({
  paths,
  viewBox = "0 0 1920 1080",
  color = "#F59E0B",
  strokeWidth = 8,
  backgroundColor = "transparent",
  drawDurationInFrames = 40,
  staggerFrames = 12,
  fillFadeInFrames = 12,
}) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  return (
    <AbsoluteFill style={{ background: backgroundColor, justifyContent: "center", alignItems: "center" }}>
      <svg
        width={width}
        height={height}
        viewBox={viewBox}
        style={{ width: "100%", height: "100%", overflow: "visible" }}
      >
        {paths.map((p, i) => {
          const start = i * staggerFrames;
          const progress = interpolate(
            frame,
            [start, start + drawDurationInFrames],
            [0, 1],
            {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.inOut(Easing.ease),
            }
          );
          const evolution = evolvePath(progress, p.d);

          const fillOpacity = p.fill
            ? interpolate(
                frame,
                [start + drawDurationInFrames, start + drawDurationInFrames + fillFadeInFrames],
                [0, 1],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
              )
            : 0;

          return (
            <g key={i}>
              {/* Fill layer fades in after the stroke completes */}
              {p.fill && (
                <path d={p.d} fill={p.fill} fillOpacity={fillOpacity} stroke="none" />
              )}
              {/* The self-drawing stroke */}
              <path
                d={p.d}
                fill="none"
                stroke={p.color ?? color}
                strokeWidth={p.strokeWidth ?? strokeWidth}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={evolution.strokeDasharray}
                strokeDashoffset={evolution.strokeDashoffset}
              />
            </g>
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};
