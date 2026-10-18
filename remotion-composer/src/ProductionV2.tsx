import React from "react";
import {
  AbsoluteFill, Audio, CalculateMetadataFunction, OffthreadVideo, Sequence, interpolate,
  useCurrentFrame, useVideoConfig,
} from "remotion";
import { resolveAsset } from "./lib/resolveAsset";

export type V2Shot = {
  id: string;
  src: string;
  from: number;
  duration: number;
  title?: string;
  typeMode?: "NONE" | "OVERLAY" | "COMPOSITIONAL" | "ENVIRONMENTAL";
  transition?: "fade" | "hard_cut_on_action" | "audio_driven_cut";
  tint?: string;
  crop?: number;
  kickTimes?: number[];
  titleAt?: number;
};

export type ProductionV2Props = {
  shots: V2Shot[];
  audioSrc?: string;
  accent?: string;
  duration: number;
  fps: number;
  width: number;
  height: number;
};

export const calculateProductionV2Metadata: CalculateMetadataFunction<ProductionV2Props> = async ({props}) => ({
  durationInFrames: Math.round(props.duration * props.fps),
  fps: props.fps, width: props.width, height: props.height,
});

const Shot: React.FC<{shot: V2Shot; accent: string}> = ({shot, accent}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const length = Math.round(shot.duration * fps);
  const fade = shot.transition === "fade" ? 10 : 0;
  const opacity = fade ? interpolate(frame, [0, fade, length - fade, length], [0, 1, 1, 0],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"}) : 1;
  const title = shot.title || "";
  const mode = shot.typeMode || "NONE";
  const titleStartFrame = shot.titleAt === undefined ? 6 : Math.round((shot.titleAt - shot.from) * fps);
  const reveal = Math.min(title.length, Math.max(0, Math.floor((frame - titleStartFrame) / 2)));
  const timelineTime = shot.from + frame / fps;
  const kickAge = (shot.kickTimes || []).reduce((age, kick) => {
    const since = timelineTime - kick;
    return since >= 0 && since < 0.12 ? Math.max(age, since) : age;
  }, Number.POSITIVE_INFINITY);
  const beatPulse = Number.isFinite(kickAge) ? 1 + 0.055 * (1 - kickAge / 0.12) : 1;
  const crop = shot.crop || 1;
  const preferredFontSize = mode === "COMPOSITIONAL" ? width * 0.11 : width * 0.065;
  const titleWidth = width * 0.88;
  // Reserve room for bold glyphs and tracking; long German compounds scale down instead of clipping.
  const fontSize = title ? Math.min(preferredFontSize, titleWidth / (title.length * 0.92)) : preferredFontSize;
  return <AbsoluteFill style={{overflow: "hidden", opacity}}>
    <AbsoluteFill style={{transform: `scale(${crop})`, filter: shot.tint ? `hue-rotate(${shot.tint})` : undefined}}>
      <OffthreadVideo src={resolveAsset(shot.src)} muted style={{width: "100%", height: "100%", objectFit: "cover"}} />
    </AbsoluteFill>
    {mode !== "NONE" && title && <AbsoluteFill style={{
      justifyContent: mode === "ENVIRONMENTAL" ? "flex-start" : "center",
      alignItems: mode === "ENVIRONMENTAL" ? "flex-end" : "center",
      padding: mode === "ENVIRONMENTAL" ? 52 : 0,
      transform: mode === "ENVIRONMENTAL" ? "perspective(900px) rotateY(-14deg)" : undefined,
    }}>
      <div style={{
        fontFamily: "Arial, sans-serif", fontWeight: 800, textTransform: "uppercase",
        boxSizing: "border-box", width: titleWidth, fontSize,
        letterSpacing: "0.14em", color: "white", textAlign: "center",
        textShadow: `0 0 24px ${accent}, 0 3px 18px #000`,
        opacity: Math.min(1, frame / 8) * Math.min(1, (length - frame) / 12),
        transform: `scale(${beatPulse})`, maxWidth: titleWidth, overflowWrap: "anywhere", lineHeight: 1.08,
      }}>{title.slice(0, reveal)}<span style={{color: accent}}>▏</span></div>
    </AbsoluteFill>}
    <div style={{position: "absolute", left: 28, bottom: 24, color: "#aaa", fontSize: height * 0.022,
                 fontFamily: "monospace", letterSpacing: "0.2em"}}>{shot.id}</div>
  </AbsoluteFill>;
};

export const ProductionV2: React.FC<ProductionV2Props> = ({shots, audioSrc, accent = "#d734a1"}) => {
  const {fps} = useVideoConfig();
  return <AbsoluteFill style={{backgroundColor: "#050209"}}>
    {shots.map((shot) => <Sequence key={shot.id} from={Math.round(shot.from * fps)}
      durationInFrames={Math.round(shot.duration * fps)}>
      <Shot shot={shot} accent={accent} />
    </Sequence>)}
    {audioSrc && <Audio src={resolveAsset(audioSrc)} volume={0.65} />}
  </AbsoluteFill>;
};
