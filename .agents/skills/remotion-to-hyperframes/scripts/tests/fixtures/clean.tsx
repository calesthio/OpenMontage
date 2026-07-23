import React, { useEffect } from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  AbsoluteFill,
  interpolate,
  spring,
  Sequence,
  staticFile,
  Audio,
  Img,
} from "remotion";

// Mount-only useEffect with empty deps + a later expression containing a
// non-empty array — regression coverage for the over-match Miguel reported:
// the earlier regex spanned past `[]` and matched `[frame]` from `pick(...)`,
// falsely flagging this clean fixture as having a blocker.
function pick<T>(_key: string, items: T[]): T {
  return items[0];
}

const TitleCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  useEffect(() => {
    console.log("mounted");
  }, []);
  const _picked = pick("x", [frame]);
  const opacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  const scale = spring({ frame, fps, config: { damping: 12 } });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ fontSize: 72, opacity, transform: `scale(${scale})` }}>Hello</div>
      <Img src={staticFile("logo.png")} />
    </AbsoluteFill>
  );
};

export const MyComposition: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0} durationInFrames={90}>
      <TitleCard />
    </Sequence>
    <Audio src={staticFile("music.mp3")} volume={0.5} />
  </AbsoluteFill>
);
