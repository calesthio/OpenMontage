import { interpolate, spring, staticFile } from "remotion";

/**
 * Shared overlay primitives for scripted screen demos.
 *
 * Extracted from ScreenshotScene so both ScreenshotScene (static image backdrop,
 * sequential timing) and ScreencastScene (video backdrop, absolute timing) can
 * reuse the exact same cursor, click-pulse, typing, bubble, highlight-box and
 * callout-balloon renderers. Coordinates are 0-1 normalized against the rendered
 * backdrop rectangle (contain-fit), so overlays track the backdrop regardless of
 * letterboxing.
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

export interface TimedStep {
  step: ScreenshotStep;
  startFrame: number;
  endFrame: number;
  /** cursor position at start of this step (inclusive) */
  cursorBefore: Point;
  /** cursor position at end of this step */
  cursorAfter: Point;
}

// ---------- Helpers ----------

export function resolveAsset(src: string): string {
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")) {
    return src;
  }
  const clean = src.replace(/^file:\/\/\/?/, "");
  if (clean.startsWith("/") || /^[A-Za-z]:[\\/]/.test(clean)) {
    return `file:///${clean.replace(/\\/g, "/")}`;
  }
  return staticFile(clean);
}

/** Compute the rendered bounding box of the backdrop inside a canvas,
 *  using object-fit: contain semantics. Returns pixel offsets/sizes. */
export function containRect(
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

// ---------- SVG cursor ----------

export const CursorArrow: React.FC<{ size?: number }> = ({ size = 28 }) => (
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

// ---------- Per-step overlay renderers ----------

export interface OverlayProps {
  timed: TimedStep;
  frame: number;
  fps: number;
  rect: { x: number; y: number; w: number; h: number };
  abs: (p: Point) => { x: number; y: number };
  absRect: (r: Region) => { left: number; top: number; width: number; height: number };
  accentColor: string;
}

export const OverlayForStep: React.FC<OverlayProps> = ({
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
