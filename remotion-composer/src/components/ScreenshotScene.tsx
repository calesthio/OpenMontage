import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

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
 * See .agents/skills/synthetic-ui-recording/SKILL.md for authoring guidance.
 */

// ---------- Types ----------

export type Region = { x: number; y: number; w: number; h: number }; // all 0-1
export type Point = [number, number]; // [x, y], 0-1 normalized

export type ScreenshotStep =
  | { kind: "cursor_move"; to: Point; durationSeconds?: number }
  | { kind: "click_pulse"; at?: Point; durationSeconds?: number; color?: string }
  | {
      kind: "type_into";
      region: Region;
      text: string;
      typeSpeed?: number; // seconds per char
      fontSize?: number; // in normalized-height units; default 0.022
      color?: string;
    }
  | {
      kind: "bubble_append";
      region: Region; // where the bubble lands (its bounding box)
      text: string;
      role?: "user" | "assistant";
      durationSeconds?: number;
      stream?: boolean; // if true, text reveals word-by-word over the duration
      fontSize?: number;
    }
  | {
      kind: "typing_dots";
      at: Point;
      durationSeconds?: number;
      color?: string;
    }
  | {
      kind: "highlight_box";
      region: Region;
      durationSeconds?: number;
      color?: string;
      pulses?: number;
    }
  | {
      kind: "callout_balloon";
      anchor: Point; // the element being pointed at
      text: string;
      position?: "top" | "bottom" | "left" | "right"; // where balloon sits relative to anchor
      durationSeconds?: number;
      color?: string;
    }
  | { kind: "pause"; seconds: number };

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

// ---------- Helpers ----------

function resolveAsset(src: string): string {
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")) {
    return src;
  }
  const clean = src.replace(/^file:\/\/\/?/, "");
  if (clean.startsWith("/") || /^[A-Za-z]:[\\/]/.test(clean)) {
    const posix = clean.replace(/\\/g, "/");
    // POSIX absolute paths already have a leading "/" — file:// + posix
    // gives exactly three slashes. Windows drive paths (C:/...) need the
    // extra slash added explicitly. Do not merge these branches — adding
    // "file:///" unconditionally double-slashes POSIX paths (file:////...).
    if (posix.startsWith("/")) {
      return `file://${posix}`;
    }
    return `file:///${posix}`;
  }
  return staticFile(clean);
}

/** Compute the rendered bounding box of the backdrop inside a canvas,
 *  using object-fit: contain semantics. Returns pixel offsets/sizes. */
function containRect(
  imgW: number,
  imgH: number,
  cvW: number,
  cvH: number
): { x: number; y: number; w: number; h: number } {
  const imgAspect = imgW / imgH;
  const cvAspect = cvW / cvH;
  if (imgAspect > cvAspect) {
    // image is wider → fit width, letterbox top/bottom
    const w = cvW;
    const h = cvW / imgAspect;
    return { x: 0, y: (cvH - h) / 2, w, h };
  } else {
    // image is taller → fit height, letterbox left/right
    const h = cvH;
    const w = cvH * imgAspect;
    return { x: (cvW - w) / 2, y: 0, w, h };
  }
}

// ---------- Timing walk — assign frame windows to each step ----------

interface TimedStep {
  step: ScreenshotStep;
  startFrame: number;
  endFrame: number;
  /** cursor position at start of this step (inclusive) */
  cursorBefore: Point;
  /** cursor position at end of this step */
  cursorAfter: Point;
}

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

// ---------- SVG cursor ----------

const CursorArrow: React.FC<{ size?: number }> = ({ size = 28 }) => (
  <svg width={size} height={size * 1.2} viewBox="0 0 16 20" style={{ display: "block" }}>
    <path
      d="M2 2 L2 16 L6 12 L8.5 17 L10.5 16 L8 11 L13 11 Z"
      fill="#FFFFFF"
      stroke="#111"
      strokeWidth={1.2}
      strokeLinejoin="round"
    />
  </svg>
);

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
  const absRect = (r: Region) => ({
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

// ---------- Per-step overlay renderers ----------

interface OverlayProps {
  timed: TimedStep;
  frame: number;
  fps: number;
  rect: { x: number; y: number; w: number; h: number };
  abs: (p: Point) => { x: number; y: number };
  absRect: (r: Region) => { left: number; top: number; width: number; height: number };
  accentColor: string;
}

const OverlayForStep: React.FC<OverlayProps> = ({
  timed,
  frame,
  fps,
  rect,
  abs,
  absRect,
  accentColor,
}) => {
  const { step, startFrame, endFrame } = timed;
  const localFrame = frame - startFrame;

  if (step.kind === "click_pulse") {
    const at = step.at ?? timed.cursorBefore;
    const p = abs(at);
    const progress = interpolate(localFrame, [0, endFrame - startFrame], [0, 1], {
      extrapolateRight: "clamp",
    });
    const size = interpolate(progress, [0, 1], [10, 80]);
    const alpha = interpolate(progress, [0, 1], [0.85, 0]);
    const color = step.color ?? accentColor;
    return (
      <div
        style={{
          position: "absolute",
          left: p.x - size / 2,
          top: p.y - size / 2,
          width: size,
          height: size,
          borderRadius: "50%",
          border: `3px solid ${color}`,
          opacity: alpha,
          pointerEvents: "none",
        }}
      />
    );
  }

  if (step.kind === "type_into") {
    const r = absRect(step.region);
    const speed = step.typeSpeed ?? 0.04;
    const totalChars = step.text.length;
    const typeFrames = totalChars * speed * fps;
    const revealed = Math.min(
      totalChars,
      Math.floor(interpolate(localFrame, [0, typeFrames], [0, totalChars], { extrapolateRight: "clamp" }))
    );
    const typed = step.text.slice(0, revealed);
    const fontPx = Math.round(rect.h * (step.fontSize ?? 0.024));
    const blink = Math.floor(frame / (fps * 0.5)) % 2 === 0;
    return (
      <div
        style={{
          position: "absolute",
          left: r.left,
          top: r.top,
          width: r.width,
          height: r.height,
          display: "flex",
          alignItems: "center",
          paddingLeft: Math.round(rect.w * 0.012),
          fontFamily: "Inter, -apple-system, sans-serif",
          fontSize: fontPx,
          color: step.color ?? "#E5E7EB",
          pointerEvents: "none",
          whiteSpace: "nowrap",
          overflow: "hidden",
        }}
      >
        <span>{typed}</span>
        {blink && (
          <span
            style={{
              display: "inline-block",
              width: 2,
              height: fontPx * 0.95,
              background: step.color ?? "#E5E7EB",
              marginLeft: 2,
            }}
          />
        )}
      </div>
    );
  }

  if (step.kind === "bubble_append") {
    const r = absRect(step.region);
    const springIn = spring({
      frame: localFrame,
      fps,
      config: { damping: 16, stiffness: 140 },
      durationInFrames: Math.ceil(fps * 0.5),
    });
    const isUser = step.role === "user";
    const fontPx = Math.round(rect.h * (step.fontSize ?? 0.021));

    // Streaming text reveal (word-by-word)
    let displayText = step.text;
    if (step.stream) {
      const words = step.text.split(/(\s+)/); // keep whitespace
      const totalRevealFrames = Math.max(1, endFrame - startFrame - fps * 0.3);
      const wordCount = words.filter((w) => w.trim()).length;
      const revealedWords = Math.floor(
        interpolate(localFrame, [fps * 0.3, fps * 0.3 + totalRevealFrames], [0, wordCount], {
          extrapolateRight: "clamp",
          extrapolateLeft: "clamp",
        })
      );
      let count = 0;
      const pieces: string[] = [];
      for (const w of words) {
        if (w.trim()) {
          if (count < revealedWords) {
            pieces.push(w);
            count++;
          } else {
            break;
          }
        } else {
          pieces.push(w);
        }
      }
      displayText = pieces.join("");
    }

    const bg = isUser ? "#2D3748" : "#1F2937";
    const border = isUser ? "#4A5568" : "#374151";

    return (
      <div
        style={{
          position: "absolute",
          left: r.left,
          top: r.top,
          width: r.width,
          minHeight: r.height,
          background: bg,
          border: `1px solid ${border}`,
          borderRadius: Math.round(rect.w * 0.008),
          padding: `${Math.round(rect.h * 0.015)}px ${Math.round(rect.w * 0.012)}px`,
          fontFamily: "Inter, -apple-system, sans-serif",
          fontSize: fontPx,
          color: "#F1F5F9",
          lineHeight: 1.5,
          opacity: springIn,
          transform: `translateY(${(1 - springIn) * 20}px)`,
          boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
          whiteSpace: "pre-wrap",
          pointerEvents: "none",
          overflow: "hidden",
        }}
      >
        {displayText}
      </div>
    );
  }

  if (step.kind === "typing_dots") {
    const p = abs(step.at);
    const dotSize = Math.round(rect.h * 0.01);
    const dots = [0, 1, 2].map((i) => {
      const phase = (frame / (fps * 0.35) - i * 0.3) % 2;
      const alpha = phase < 1 ? 0.3 + phase * 0.7 : 1 - (phase - 1) * 0.7;
      return alpha;
    });
    const color = step.color ?? accentColor;
    return (
      <div
        style={{
          position: "absolute",
          left: p.x,
          top: p.y,
          display: "flex",
          gap: dotSize * 0.7,
          pointerEvents: "none",
        }}
      >
        {dots.map((a, i) => (
          <div
            key={i}
            style={{
              width: dotSize,
              height: dotSize,
              borderRadius: "50%",
              background: color,
              opacity: Math.max(0.3, a),
            }}
          />
        ))}
      </div>
    );
  }

  if (step.kind === "highlight_box") {
    const r = absRect(step.region);
    const dur = endFrame - startFrame;
    const pulses = step.pulses ?? 2;
    const color = step.color ?? accentColor;
    // Pulsing ring: oscillate opacity + scale
    const wave = Math.sin((localFrame / dur) * pulses * Math.PI * 2) * 0.5 + 0.5;
    const alpha = 0.4 + wave * 0.5;
    const glow = 10 + wave * 18;
    return (
      <div
        style={{
          position: "absolute",
          left: r.left - 6,
          top: r.top - 6,
          width: r.width + 12,
          height: r.height + 12,
          border: `3px solid ${color}`,
          borderRadius: Math.round(rect.w * 0.006),
          boxShadow: `0 0 ${glow}px ${color}`,
          opacity: alpha,
          pointerEvents: "none",
        }}
      />
    );
  }

  if (step.kind === "callout_balloon") {
    const a = abs(step.anchor);
    const pos = step.position ?? "top";
    const springIn = spring({
      frame: localFrame,
      fps,
      config: { damping: 14, stiffness: 160 },
      durationInFrames: Math.ceil(fps * 0.4),
    });
    const dur = endFrame - startFrame;
    const fadeOut = interpolate(
      localFrame,
      [dur - fps * 0.4, dur],
      [1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    const alpha = Math.min(springIn, fadeOut);
    const color = step.color ?? accentColor;
    const fontPx = Math.round(rect.h * 0.024);
    const maxW = rect.w * 0.28;

    // Balloon offset from anchor
    const offset = rect.h * 0.06;
    let bx = a.x;
    let by = a.y;
    let tailStyle: React.CSSProperties = {};
    if (pos === "top") {
      by = a.y - offset - fontPx * 2.5;
      bx = a.x - maxW / 2;
      tailStyle = {
        position: "absolute",
        bottom: -10,
        left: "50%",
        transform: "translateX(-50%)",
        width: 0,
        height: 0,
        borderLeft: "10px solid transparent",
        borderRight: "10px solid transparent",
        borderTop: `12px solid ${color}`,
      };
    } else if (pos === "bottom") {
      by = a.y + offset;
      bx = a.x - maxW / 2;
      tailStyle = {
        position: "absolute",
        top: -10,
        left: "50%",
        transform: "translateX(-50%)",
        width: 0,
        height: 0,
        borderLeft: "10px solid transparent",
        borderRight: "10px solid transparent",
        borderBottom: `12px solid ${color}`,
      };
    } else if (pos === "left") {
      bx = a.x - offset - maxW;
      by = a.y - fontPx;
      tailStyle = {
        position: "absolute",
        right: -10,
        top: "50%",
        transform: "translateY(-50%)",
        width: 0,
        height: 0,
        borderTop: "10px solid transparent",
        borderBottom: "10px solid transparent",
        borderLeft: `12px solid ${color}`,
      };
    } else {
      bx = a.x + offset;
      by = a.y - fontPx;
      tailStyle = {
        position: "absolute",
        left: -10,
        top: "50%",
        transform: "translateY(-50%)",
        width: 0,
        height: 0,
        borderTop: "10px solid transparent",
        borderBottom: "10px solid transparent",
        borderRight: `12px solid ${color}`,
      };
    }

    return (
      <div
        style={{
          position: "absolute",
          left: Math.max(rect.x + 8, Math.min(rect.x + rect.w - maxW - 8, bx)),
          top: by,
          width: maxW,
          background: color,
          color: "#0B0F1A",
          fontFamily: "Inter, -apple-system, sans-serif",
          fontWeight: 600,
          fontSize: fontPx,
          lineHeight: 1.35,
          padding: `${Math.round(fontPx * 0.6)}px ${Math.round(fontPx * 0.9)}px`,
          borderRadius: Math.round(rect.w * 0.008),
          opacity: alpha,
          transform: `scale(${interpolate(springIn, [0, 1], [0.9, 1])})`,
          boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
          pointerEvents: "none",
        }}
      >
        {step.text}
        <div style={tailStyle} />
      </div>
    );
  }

  return null;
};
