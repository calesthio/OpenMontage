import {
  AbsoluteFill,
  Img,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  containRect,
  CursorArrow,
  OverlayForStep,
  resolveAsset,
  type Point,
  type ScreenshotStep,
  type TimedStep,
} from "./overlayPrimitives";

// Re-export the shared types so existing importers (Explainer, index) keep
// importing them from "./ScreenshotScene".
export type { Region, Point, ScreenshotStep } from "./overlayPrimitives";

/**
 * ScreenshotScene — approach-1 synthetic UI demo.
 *
 * Takes any screenshot as a frozen backdrop and animates scripted overlays
 * (cursor, click pulses, typing, chat bubbles, highlight rings, callouts)
 * on top at normalized coordinates. Viewer-indistinguishable from a real
 * screen recording for ~15-30s focused demos.
 *
 * Coordinate system: everything is 0-1 normalized against the rendered
 * backdrop rectangle (not the raw canvas), so overlays track the image
 * correctly regardless of letterboxing.
 *
 * For a MOVING backdrop (a real screen recording) with absolute-time overlays,
 * see ScreencastScene, which reuses the same overlay primitives.
 */

interface ScreenshotSceneProps {
  backgroundImage: string;
  /** Natural pixel size of the image — used to compute the contain-fit
   *  rectangle so overlays land on correct pixels. Defaults to 16:9. */
  backgroundSize?: { width: number; height: number };
  steps: ScreenshotStep[];
  accentColor?: string;
  /** Starting cursor position. Default: top-right area. */
  cursorStartAt?: Point;
}

// ---------- Timing walk — assign frame windows to each step ----------

function walkTimeline(
  steps: ScreenshotStep[],
  fps: number,
  cursorStart: Point
): { timed: TimedStep[]; totalFrames: number } {
  const timed: TimedStep[] = [];
  let cursor = cursorStart;
  let frameCursor = 0;

  for (const step of steps) {
    let duration = 0;
    const before = cursor;
    let after = cursor;
    let blocks = true; // whether step advances timeline cursor

    switch (step.kind) {
      case "cursor_move":
        duration = (step.durationSeconds ?? 0.9) * fps;
        after = step.to;
        break;
      case "click_pulse":
        duration = (step.durationSeconds ?? 0.45) * fps;
        if (step.at) after = step.at;
        break;
      case "type_into": {
        const speed = step.typeSpeed ?? 0.04;
        duration = step.text.length * speed * fps + 0.25 * fps;
        break;
      }
      case "bubble_append":
        duration = (step.durationSeconds ?? 0.9) * fps;
        break;
      case "typing_dots":
        duration = (step.durationSeconds ?? 1.2) * fps;
        break;
      case "highlight_box":
        duration = (step.durationSeconds ?? 1.5) * fps;
        blocks = false; // non-blocking — subsequent steps can overlap
        break;
      case "callout_balloon":
        duration = (step.durationSeconds ?? 2.2) * fps;
        blocks = false;
        break;
      case "pause":
        duration = step.seconds * fps;
        break;
    }

    timed.push({
      step,
      startFrame: Math.round(frameCursor),
      endFrame: Math.round(frameCursor + duration),
      cursorBefore: before,
      cursorAfter: after,
    });
    cursor = after;
    if (blocks) frameCursor += duration;
  }

  const totalFrames = Math.max(
    ...timed.map((t) => t.endFrame),
    Math.round(frameCursor)
  );
  return { timed, totalFrames };
}

// ---------- Main component ----------

export const ScreenshotScene: React.FC<ScreenshotSceneProps> = ({
  backgroundImage,
  backgroundSize,
  steps,
  accentColor = "#F59E0B",
  cursorStartAt = [0.95, 0.05],
}) => {
  const frame = useCurrentFrame();
  const { fps, width: cvW, height: cvH } = useVideoConfig();

  const imgW = backgroundSize?.width ?? 1920;
  const imgH = backgroundSize?.height ?? 1080;
  const rect = containRect(imgW, imgH, cvW, cvH);

  // Convert normalized (0-1) backdrop coord to absolute canvas pixels
  const abs = (p: Point): { x: number; y: number } => ({
    x: rect.x + p[0] * rect.w,
    y: rect.y + p[1] * rect.h,
  });
  const absRect = (r: { x: number; y: number; w: number; h: number }) => ({
    left: rect.x + r.x * rect.w,
    top: rect.y + r.y * rect.h,
    width: r.w * rect.w,
    height: r.h * rect.h,
  });

  // Walk timeline once
  const { timed } = walkTimeline(steps, fps, cursorStartAt);

  // --- Cursor position at current frame ---
  // Find the active cursor_move or the completed-most-recent one.
  let cursorPos = cursorStartAt;
  for (const t of timed) {
    if (frame >= t.endFrame) {
      cursorPos = t.cursorAfter;
    } else if (frame >= t.startFrame && t.step.kind === "cursor_move") {
      const p = interpolate(frame, [t.startFrame, t.endFrame], [0, 1], {
        extrapolateRight: "clamp",
      });
      // Ease-out so cursor decelerates as it arrives
      const eased = 1 - Math.pow(1 - p, 3);
      cursorPos = [
        t.cursorBefore[0] + (t.cursorAfter[0] - t.cursorBefore[0]) * eased,
        t.cursorBefore[1] + (t.cursorAfter[1] - t.cursorBefore[1]) * eased,
      ];
      break;
    } else if (frame < t.startFrame) {
      cursorPos = t.cursorBefore;
      break;
    }
  }

  const cursorAbs = abs(cursorPos);

  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {/* Backdrop */}
      <Img
        src={resolveAsset(backgroundImage)}
        style={{
          position: "absolute",
          left: rect.x,
          top: rect.y,
          width: rect.w,
          height: rect.h,
          objectFit: "fill",
        }}
      />

      {/* Overlays — render in order so later steps paint on top.
          Sticky kinds (type_into, bubble_append) persist once they appear;
          transient kinds fade out after their duration. */}
      {timed.map((t, i) => {
        const kind = t.step.kind;
        const sticky = kind === "type_into" || kind === "bubble_append";
        const active = sticky
          ? frame >= t.startFrame
          : frame >= t.startFrame && frame <= t.endFrame + fps * 0.4;
        if (!active) return null;
        return (
          <OverlayForStep
            key={i}
            timed={t}
            frame={frame}
            fps={fps}
            rect={rect}
            abs={abs}
            absRect={absRect}
            accentColor={accentColor}
          />
        );
      })}

      {/* Cursor — always on top */}
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
  );
};
