// AI-generated-content label (《人工智能生成合成内容标识办法》, in force
// 2025-09-01): every final video must show an explicit "AI生成" label on its
// opening frames. This is the Remotion half of that requirement — the render
// caller (tools/video/video_compose.py::_remotion_render) injects an
// `aigcLabel` prop into every templated render by default; withAigcLabel
// (applied to every <Composition> in Root.tsx) renders the badge whenever
// that prop is present. The implicit (metadata) half is embedded after the
// render by tools/video/aigc_label.py.
//
// This is a reserved compliance layer, NOT a creative overlay: it sits above
// every scene/overlay/caption layer, uses real DOM text with the bundled CJK
// fallback (never baked-in glyphs), and only the loud config-level opt-out
// (config.yaml aigc_label.enabled=false) removes it.

import React from "react";
import { AbsoluteFill, Sequence, useVideoConfig } from "remotion";
import { withCjkFallback } from "./fonts";

export type AigcLabelProps = {
  text?: string;
  seconds?: number;
};

export const AigcBadge: React.FC<AigcLabelProps> = ({
  text = "AI生成",
  seconds = 4,
}) => {
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const labelFrames = Math.min(
    durationInFrames,
    Math.max(1, Math.ceil(fps * seconds)),
  );
  // Practice-guide minimum: text height ~5% of the shorter edge.
  const fontSize = Math.max(20, Math.round(Math.min(width, height) * 0.05));
  const pad = Math.round(fontSize * 0.55);
  return (
    <Sequence from={0} durationInFrames={labelFrames} name="AIGC label">
      <AbsoluteFill style={{ pointerEvents: "none", zIndex: 9999 }}>
        <div
          style={{
            position: "absolute",
            top: pad,
            right: pad,
            fontFamily: withCjkFallback("system-ui"),
            fontSize,
            lineHeight: 1.2,
            color: "rgba(255,255,255,0.92)",
            background: "rgba(0,0,0,0.4)",
            padding: `${Math.round(fontSize * 0.25)}px ${Math.round(fontSize * 0.6)}px`,
            borderRadius: Math.round(fontSize * 0.4),
          }}
        >
          {text}
        </div>
      </AbsoluteFill>
    </Sequence>
  );
};

/**
 * Wraps a top-level composition component so it renders the AIGC badge when
 * an `aigcLabel` prop is present (injected by video_compose for every
 * templated render). The wrapped component's own props pass through
 * untouched — compositions don't need to know the badge exists.
 */
export function withAigcLabel<P extends object>(
  Component: React.ComponentType<P>,
): React.FC<P & { aigcLabel?: AigcLabelProps | null }> {
  const Wrapped: React.FC<P & { aigcLabel?: AigcLabelProps | null }> = (
    props,
  ) => {
    const { aigcLabel, ...rest } = props;
    return (
      <>
        <Component {...(rest as P)} />
        {aigcLabel ? <AigcBadge {...aigcLabel} /> : null}
      </>
    );
  };
  Wrapped.displayName = `withAigcLabel(${Component.displayName ?? Component.name ?? "Component"})`;
  return Wrapped;
}
