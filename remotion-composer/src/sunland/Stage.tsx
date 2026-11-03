import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate, Easing } from "remotion";

export const SETTLE = Easing.bezier(0.22, 0.61, 0.21, 1);
export const ease = (f: number, a: number, b: number, from: number, to: number) =>
  interpolate(f, [a, b], [from, to], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: SETTLE,
  });

/* A real perspective stage. Children live in 3D space, so translateZ actually
   reads as depth rather than scale, and the camera can move around them. */
export const Stage: React.FC<{
  children: React.ReactNode;
  /* camera drift over the beat: [fromDeg, toDeg] yaw, and dolly in px of Z */
  yaw?: [number, number];
  pitch?: [number, number];
  dolly?: [number, number];
  dur: number;
  bg?: string;
}> = ({ children, yaw = [0, 0], pitch = [0, 0], dolly = [0, 0], dur, bg }) => {
  const f = useCurrentFrame();
  const y = ease(f, 0, dur, yaw[0], yaw[1]);
  const p = ease(f, 0, dur, pitch[0], pitch[1]);
  const z = ease(f, 0, dur, dolly[0], dolly[1]);
  return (
    <AbsoluteFill style={{ background: bg, perspective: 1700, perspectiveOrigin: "50% 42%" }}>
      <AbsoluteFill style={{
        transformStyle: "preserve-3d",
        transform: `translateZ(${z}px) rotateY(${y}deg) rotateX(${p}deg)`,
      }}>
        {children}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/* deterministic pseudo-random so every render is identical */
const rnd = (i: number, s: number) => {
  const x = Math.sin(i * 127.1 + s * 311.7) * 43758.5453;
  return x - Math.floor(x);
};

/* Bokeh at genuine depths — far motes are blurred and drift slower, which is
   what makes the frame feel like it has air in it rather than being a flat card. */
export const Bokeh: React.FC<{ count?: number; tint?: string; dur: number; warm?: boolean }> = ({
  count = 16, tint = "#FFFFFF", dur, warm = false,
}) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ transformStyle: "preserve-3d", pointerEvents: "none" }}>
      {new Array(count).fill(0).map((_, i) => {
        const depth = -900 + rnd(i, 1) * 1500;
        const size = 26 + rnd(i, 2) * 150;
        const x = rnd(i, 3) * 1080;
        const y0 = rnd(i, 4) * 1920;
        const drift = (0.25 + rnd(i, 5) * 0.9) * (depth < 0 ? 1 : 1.7);
        const y = y0 - (f * drift) % 2200;
        const blur = Math.abs(depth) / 90 + 6;
        const op = (0.05 + rnd(i, 6) * 0.17) * ease(f, 0, 30, 0, 1);
        const c = warm && i % 3 === 0 ? "#F6C98A" : tint;
        return (
          <div key={i} style={{
            position: "absolute", left: x, top: y, width: size, height: size,
            borderRadius: "50%", background: c, opacity: op,
            filter: `blur(${blur}px)`, transform: `translateZ(${depth}px)`,
          }} />
        );
      })}
    </AbsoluteFill>
  );
};

/* a soft volumetric shaft — gives the dark beat a light source */
export const LightShaft: React.FC<{ dur: number }> = ({ dur }) => {
  const f = useCurrentFrame();
  const o = ease(f, 0, 44, 0, 0.5);
  const sway = Math.sin(f / 46) * 3;
  return (
    <div style={{
      position: "absolute", top: -420, left: "50%", width: 980, height: 2400,
      transform: `translateX(-50%) rotate(${12 + sway}deg) translateZ(-420px)`,
      background: "linear-gradient(to bottom, rgba(255,243,226,0.30) 0%, rgba(255,243,226,0.06) 45%, rgba(255,243,226,0) 78%)",
      filter: "blur(46px)", opacity: o, pointerEvents: "none",
    }} />
  );
};

/* text that arrives out of depth, focus pulling in as it lands */
export const DepthLine: React.FC<{
  children: React.ReactNode; delay: number; size: number;
  color?: string; font?: string; z?: number; weightShadow?: boolean;
}> = ({ children, delay, size, color = "#16130F", font = "PoppinsB", z = -520, weightShadow = false }) => {
  const f = useCurrentFrame();
  const t = ease(f, delay, delay + 26, 0, 1);
  const zz = z * (1 - t);
  const blur = (1 - t) * 13;
  return (
    <div style={{
      opacity: Math.min(1, t * 1.5), transform: `translateZ(${zz}px)`,
      filter: `blur(${blur}px)`, color, fontFamily: font, fontSize: size,
      lineHeight: 1.08, letterSpacing: "-0.022em", textAlign: "center",
      textShadow: weightShadow ? "0 26px 50px rgba(60,40,20,0.18)" : undefined,
    }}>{children}</div>
  );
};
