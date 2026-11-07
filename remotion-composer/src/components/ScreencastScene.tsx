import {
  AbsoluteFill,
  interpolate,
  OffthreadVideo,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  containRect,
  CursorArrow,
  OverlayForStep,
  resolveAsset,
  type Point,
  type Region,
  type ScreenshotStep,
  type TimedStep,
} from "./overlayPrimitives";

/**
 * ScreencastScene — approach-2: animated overlays over a MOVING screen recording.
 *
 * Where ScreenshotScene animates overlays over a frozen image with sequential
 * timing, ScreencastScene plays a real capture (OffthreadVideo) and drives the
 * SAME overlay primitives (highlight_box, callout_balloon, cursor, click_pulse,
 * …) by ABSOLUTE video timestamps, plus an optional zoom-to-highlight. This is
 * the v2 render for Cypress-driven tutorial videos: the step timestamps and the
 * real element bounding boxes come from the capture manifest, so callouts land
 * exactly on the buttons/fields with no manual tuning.
 *
 * Coordinates are 0-1 normalized against the video's contain-fit rectangle.
 */

/** An overlay is any ScreenshotStep placed on an absolute [atSeconds, untilSeconds] window. */
export type ScreencastOverlay = { atSeconds: number; untilSeconds: number } & ScreenshotStep;

/** Cursor waypoint: the cursor eases toward `to` arriving at `atSeconds`. */
export type CursorKeyframe = { atSeconds: number; to: Point };

/** Zoom-to-highlight window: scale toward `region`'s center during the window. */
export type ZoomWindow = {
  atSeconds: number;
  untilSeconds: number;
  region: Region;
  scale?: number; // default 1.6
};

interface ScreencastSceneProps {
  /** The recorded capture (file path or URL). */
  source: string;
  /** Seek this many seconds into the source before playback. */
  sourceInSeconds?: number;
  /** Natural pixel size of the video for contain-fit math. Defaults to the canvas. */
  backgroundSize?: { width: number; height: number };
  overlays?: ScreencastOverlay[];
  cursor?: CursorKeyframe[];
  zoom?: ZoomWindow[];
  accentColor?: string;
  cursorStartAt?: Point;
}

export const ScreencastScene: React.FC<ScreencastSceneProps> = ({
  source,
  sourceInSeconds = 0,
  backgroundSize,
  overlays = [],
  cursor = [],
  zoom = [],
  accentColor = "#F59E0B",
  cursorStartAt = [0.95, 0.05],
}) => {
  const frame = useCurrentFrame();
  const { fps, width: cvW, height: cvH } = useVideoConfig();
  const t = frame / fps;

  const imgW = backgroundSize?.width ?? cvW;
  const imgH = backgroundSize?.height ?? cvH;
  const rect = containRect(imgW, imgH, cvW, cvH);

  const abs = (p: Point): { x: number; y: number } => ({
    x: rect.x + p[0] * rect.w,
    y: rect.y + p[1] * rect.h,
  });
  const absRect = (r: Region) => ({
    left: rect.x + r.x * rect.w,
    top: rect.y + r.y * rect.h,
    width: r.w * rect.w,
    height: r.h * rect.h,
  });

  // --- Zoom-to-highlight for the current frame (scale around the region center) ---
  let zScale = 1;
  let zx = cvW / 2;
  let zy = cvH / 2;
  for (const z of zoom) {
    if (t >= z.atSeconds && t <= z.untilSeconds) {
      const a = z.atSeconds * fps;
      const b = Math.max(z.untilSeconds * fps, a + 2); // >= 2 frames keeps ranges valid
      const target = z.scale ?? 1.6;
      const ramp = Math.max(1, Math.min(0.5 * fps, (b - a) / 2));
      // interpolate() requires a STRICTLY increasing input range. For short zoom
      // windows a+ramp === b-ramp, which throws — so short windows use a single
      // triangle peak (ramp in, ramp out) instead of an in/hold/out.
      const hold = a + ramp < b - ramp;
      zScale = interpolate(
        frame,
        hold ? [a, a + ramp, b - ramp, b] : [a, (a + b) / 2, b],
        hold ? [1, target, target, 1] : [1, target, 1],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
      );
      const c = absRect(z.region);
      zx = c.left + c.width / 2;
      zy = c.top + c.height / 2;
      break;
    }
  }

  // --- Cursor position (ease between waypoints by wall-clock time) ---
  // Prepend an implicit waypoint at t=0 at cursorStartAt so the cursor rests at
  // its start position and eases INTO the first target, rather than being pinned
  // to the first target for the whole preroll.
  const kf: CursorKeyframe[] =
    cursor.length === 0
      ? [{ atSeconds: 0, to: cursorStartAt }]
      : cursor[0].atSeconds > 0
        ? [{ atSeconds: 0, to: cursorStartAt }, ...cursor]
        : cursor;
  const cursorAt = (tt: number): Point => {
    if (tt <= kf[0].atSeconds) return kf[0].to;
    if (tt >= kf[kf.length - 1].atSeconds) return kf[kf.length - 1].to;
    for (let i = 0; i < kf.length - 1; i++) {
      const c0 = kf[i];
      const c1 = kf[i + 1];
      if (c1.atSeconds <= c0.atSeconds) continue; // skip duplicate/degenerate stamps
      if (tt >= c0.atSeconds && tt <= c1.atSeconds) {
        const p = interpolate(tt, [c0.atSeconds, c1.atSeconds], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const eased = 1 - Math.pow(1 - p, 3);
        return [
          c0.to[0] + (c1.to[0] - c0.to[0]) * eased,
          c0.to[1] + (c1.to[1] - c0.to[1]) * eased,
        ];
      }
    }
    return kf[kf.length - 1].to;
  };
  const cursorPos = cursorAt(t);
  const cursorAbs = abs(cursorPos);

  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {/* Everything (video + overlays + cursor) shares one zoom transform so
          callouts stay glued to their targets when we zoom in. */}
      <AbsoluteFill
        style={{ transform: `scale(${zScale})`, transformOrigin: `${zx}px ${zy}px` }}
      >
        <OffthreadVideo
          src={resolveAsset(source)}
          startFrom={Math.round(sourceInSeconds * fps)}
          muted
          style={{
            position: "absolute",
            left: rect.x,
            top: rect.y,
            width: rect.w,
            height: rect.h,
            objectFit: "fill",
          }}
        />

        {overlays.map((o, i) => {
          const startFrame = Math.round(o.atSeconds * fps);
          const endFrame = Math.round(o.untilSeconds * fps);
          // Over a MOVING capture every overlay respects its [at, until] window
          // (no sticky-forever like the static ScreenshotScene) — otherwise a
          // type_into/bubble_append stays glued on after the app navigates away.
          if (frame < startFrame || frame > endFrame + fps * 0.4) return null;
          // Freeze a click_pulse's implicit anchor to the cursor position at the
          // pulse's start, so it doesn't smear along the live moving cursor.
          const anchor = cursorAt(o.atSeconds);
          const timed: TimedStep = {
            step: o,
            startFrame,
            endFrame,
            cursorBefore: anchor,
            cursorAfter: anchor,
          };
          return (
            <OverlayForStep
              key={i}
              timed={timed}
              frame={frame}
              fps={fps}
              rect={rect}
              abs={abs}
              absRect={absRect}
              accentColor={accentColor}
            />
          );
        })}

        <div
          style={{
            position: "absolute",
            left: cursorAbs.x - 4,
            top: cursorAbs.y - 2,
            pointerEvents: "none",
            filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.4))",
          }}
        >
          <CursorArrow size={Math.round(rect.w * 0.018)} />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
