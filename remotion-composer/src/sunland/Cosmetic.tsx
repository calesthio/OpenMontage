import React from "react";
import {
  AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig,
  interpolate, Easing, staticFile, Img,
} from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { flip } from "@remotion/transitions/flip";
import { ToothDefs, Tooth, Gums, Veneer, CENTRAL, LATERAL } from "./Teeth";
import { Stage, Bokeh, LightShaft } from "./Stage";

/* ── tokens (see art-direction.md) ───────────────────────────────── */
const INK = "#16130F";
const CREAM = "#F7EEE5";
const BRAND = "#E3092F";
const GOLD = "#E4C78D";
const SOFT = "#6E675F";
const BOLD = "PoppinsB";
const LIGHT = "PoppinsL";
const MED = "PoppinsM";

export const Fonts: React.FC = () => (
  <style>{`
    @font-face{font-family:${BOLD};src:url("${staticFile("fonts/Poppins-Bold.ttf")}")format("truetype");font-display:block}
    @font-face{font-family:${MED};src:url("${staticFile("fonts/Poppins-Medium.ttf")}")format("truetype");font-display:block}
    @font-face{font-family:${LIGHT};src:url("${staticFile("fonts/Poppins-Light.ttf")}")format("truetype");font-display:block}
  `}</style>
);

const SETTLE = Easing.bezier(0.22, 0.61, 0.21, 1);
const ease = (f: number, a: number, b: number, from: number, to: number) =>
  interpolate(f, [a, b], [from, to], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: SETTLE,
  });

const Rise: React.FC<{
  children: React.ReactNode; delay: number; size: number;
  color?: string; font?: string; lh?: number; track?: number;
}> = ({ children, delay, size, color = INK, font = BOLD, lh = 1.1, track = -0.02 }) => {
  const f = useCurrentFrame();
  return (
    <div style={{
      opacity: ease(f, delay, delay + 16, 0, 1),
      transform: `translateY(${ease(f, delay, delay + 20, 26, 0)}px)`,
      color, fontFamily: font, fontSize: size, lineHeight: lh,
      letterSpacing: `${track}em`, textAlign: "center",
    }}>{children}</div>
  );
};

/* ── 1. hook — type on near-black ────────────────────────────────── */
const Hook: React.FC = () => {
  const f = useCurrentFrame();
  const rule = ease(f, 52, 78, 0, 1);
  return (
    <Stage bg={INK} yaw={[2.2,-1.5]} dolly={[-120,55]} dur={144}><LightShaft dur={144} /><Bokeh count={14} tint="#FFE9C9" dur={144} warm /><AbsoluteFill style={{ background: INK, justifyContent: "center", padding: "0 84px" }}>
      <div style={{
        position: "absolute", top: "4%", left: "50%", width: 1400, height: 1400,
        transform: "translateX(-50%)", borderRadius: "50%",
        opacity: ease(f, 0, 54, 0.08, 0.36),
        background: "radial-gradient(circle, rgba(255,249,240,0.24) 0%, rgba(255,249,240,0) 62%)",
      }} />
      <div style={{ position: "relative" }}>
        <Rise delay={4} size={116} color="#FBF6EF">Most people</Rise>
        <Rise delay={14} size={116} color="#FBF6EF">asking for veneers</Rise>
        <div style={{ height: 30 }} />
        <Rise delay={32} size={116} color="#FFFFFF">don&rsquo;t need them.</Rise>
        <div style={{
          margin: "46px auto 0", height: 5, width: rule * 270,
          background: BRAND, borderRadius: 3,
        }} />
      </div>
    </AbsoluteFill></Stage>
  );
};

/* ── 2. a shade guide — the object that answers "is it just colour?" ── */
const ShadeGuide: React.FC = () => {
  const f = useCurrentFrame();
  const shades = ["#C7A478", "#D5B590", "#E2C8A8", "#EDDCC5", "#F8F1E6"];
  const picked = 3;
  return (
    <Stage bg={CREAM} yaw={[-5,2.5]} dolly={[-55,35]} dur={162}><Bokeh count={8} tint="#FFFFFF" dur={200} warm /><AbsoluteFill style={{ background: CREAM, justifyContent: "center", alignItems: "center" }}>
      <svg width="1000" height="560" viewBox="-250 -70 500 280" style={{ marginTop: -210 }}>
        <ToothDefs />
        {shades.map((c, i) => {
          const x = -190 + i * 95;
          const inn = ease(f, 4 + i * 6, 30 + i * 6, 0, 1);
          const isP = i === picked;
          const lift = isP ? ease(f, 66, 100, 0, -34) : 0;
          const fade = isP ? 1 : ease(f, 74, 104, 1, 0.3);
          return (
            <g key={c} transform={`translate(${x} ${lift}) scale(0.82)`} opacity={inn * fade}>
              {/* metal handle of the shade tab */}
              <rect x="-9" y="-56" width="18" height="56" rx="6" fill="#C2BAB0" />
              <rect x="-9" y="-56" width="7" height="56" rx="4" fill="#DCD5CC" />
              <path d={CENTRAL} fill={c} />
              <path d={CENTRAL} fill="url(#incisal)" opacity="0.5" />
              <ellipse cx="-13" cy="34" rx="8" ry="24" fill="#FFF" opacity="0.4"
                       transform="rotate(-7 -13 34)" />
              <path d={CENTRAL} fill="none" stroke="#B9A98F" strokeOpacity="0.5" strokeWidth="1.2" />
              {isP && (
                <circle cx="0" cy="138" r="6" fill={BRAND}
                        opacity={ease(f, 80, 100, 0, 1)} />
              )}
            </g>
          );
        })}
      </svg>
      <div style={{ position: "absolute", bottom: 420, width: "100%", padding: "0 80px" }}>
        <Rise delay={10} size={80}>Often it&rsquo;s just shade.</Rise>
        <div style={{ height: 18 }} />
        <Rise delay={72} size={80}>
          Or <span style={{ color: BRAND }}>one chipped edge</span>.
        </Rise>
      </div>
    </AbsoluteFill></Stage>
  );
};

/* ── 3. a measured line — time ───────────────────────────────────── */
const Since: React.FC = () => {
  const f = useCurrentFrame();
  const draw = ease(f, 10, 76, 0, 1);
  const dot = ease(f, 62, 86, 0, 1);
  return (
    <Stage bg={CREAM} yaw={[4,-2.5]} dolly={[-40,28]} dur={153}><Bokeh count={8} tint="#FFFFFF" dur={200} warm /><AbsoluteFill style={{ background: CREAM, justifyContent: "center" }}>
      <div style={{ padding: "0 96px" }}>
        <Rise delay={2} size={30} font={MED} color={SOFT} track={0.18}>
          SAME CORNER OF FOOTHILL
        </Rise>
        <div style={{ height: 96 }} />
        <div style={{ position: "relative", height: 152 }}>
          <div style={{ position: "absolute", top: 72, left: 0, height: 2, width: `${draw * 100}%`, background: "#C9BCAC" }} />
          <div style={{ position: "absolute", top: 58, left: 0, width: 3, height: 30, background: INK, opacity: ease(f, 10, 26, 0, 1) }} />
          <div style={{ position: "absolute", top: 50, right: 0, width: 5, height: 46, background: BRAND, opacity: dot }} />
          <div style={{ position: "absolute", top: 0, left: 0, fontFamily: BOLD, fontSize: 46, color: INK, opacity: ease(f, 14, 32, 0, 1) }}>1991</div>
          <div style={{ position: "absolute", top: 106, right: 0, fontFamily: MED, fontSize: 30, color: SOFT, opacity: dot }}>today</div>
        </div>
        <div style={{ height: 74 }} />
        <Rise delay={48} size={94}>
          Thirty&#8209;five years in <span style={{ color: BRAND }}>one</span> chair.
        </Rise>
      </div>
    </AbsoluteFill></Stage>
  );
};

/* ── 4. signature device — the shell settles onto a central incisor ── */
const VeneerBeat: React.FC = () => {
  const f = useCurrentFrame();
  const inn = ease(f, 0, 28, 0, 1);
  const drop = ease(f, 30, 86, -270, 0);
  const shellO = ease(f, 30, 52, 0, 1);
  const sweep = ease(f, 84, 128, -22, 122);
  const bright = ease(f, 92, 124, 0, 1);
  const zoom = ease(f, 0, 210, 1.0, 1.08);
  return (
    <Stage bg={CREAM} yaw={[-6,4]} dolly={[-190,110]} dur={228}><Bokeh count={8} tint="#FFFFFF" dur={200} warm /><AbsoluteFill style={{ background: CREAM, justifyContent: "center", alignItems: "center" }}>
      <div style={{
        position: "absolute", width: 1150, height: 1150, borderRadius: "50%", marginTop: -230,
        background: "radial-gradient(circle, rgba(255,255,255,0.92) 0%, rgba(247,238,229,0) 66%)",
      }} />
      <svg width="1080" height="684" viewBox="-150 -26 300 190"
           style={{ marginTop: -210, transform: `scale(${zoom})`, opacity: inn }}>
        <ToothDefs />
        <ellipse cx="0" cy="126" rx="150" ry="11" fill="#C3B2A0" opacity="0.26" />
        <Tooth d={LATERAL} x={-116} />
        <Tooth d={CENTRAL} x={-43} bright={bright} />
        <Tooth d={CENTRAL} x={43} />
        <Tooth d={LATERAL} x={116} />
        <Gums />
        <g transform="translate(-43 0)">
          <Veneer opacity={shellO} dy={drop} sweep={sweep} />
        </g>
      </svg>
      <div style={{ position: "absolute", bottom: 360, width: "100%", padding: "0 80px" }}>
        <Rise delay={104} size={62}>Porcelain. Half a millimetre.</Rise>
        <div style={{ height: 18 }} />
        <Rise delay={140} size={62} color={SOFT} font={LIGHT}>
          The <span style={{ color: BRAND, fontFamily: BOLD }}>last</span> option, not the first.
        </Rise>
      </div>
    </AbsoluteFill></Stage>
  );
};

/* ── 5. three marks ──────────────────────────────────────────────── */
const Marks: React.FC = () => {
  const f = useCurrentFrame();
  const items = [
    {
      label: "Veneers",
      draw: (p: number) => (
        <path d={CENTRAL} fill="none" stroke={INK} strokeWidth="4.5"
              strokeDasharray="420" strokeDashoffset={420 * (1 - p)}
              transform="translate(0 -52) scale(0.95)" />
      ),
    },
    {
      label: "Whitening",
      draw: (p: number) => (
        <g opacity={p} transform="translate(0 -4)">
          <circle cx="0" cy="0" r="40" fill="none" stroke={INK} strokeWidth="4.5" />
          {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
            <line key={a} x1="0" y1="-58" x2="0" y2="-72" stroke={BRAND} strokeWidth="4.5"
                  strokeLinecap="round" transform={`rotate(${a + p * 22} 0 0)`} />
          ))}
        </g>
      ),
    },
    {
      label: "Smile makeovers",
      draw: (p: number) => (
        <path d="M -58,-18 C -38,44 38,44 58,-18" fill="none" stroke={INK} strokeWidth="6"
              strokeLinecap="round" strokeDasharray="170" strokeDashoffset={170 * (1 - p)} />
      ),
    },
  ];
  return (
    <Stage bg={CREAM} yaw={[6,-4]} dolly={[-70,45]} dur={153}><Bokeh count={8} tint="#FFFFFF" dur={200} warm /><AbsoluteFill style={{ background: CREAM, justifyContent: "center", alignItems: "center" }}>
      <div style={{ display: "flex", gap: 10, marginTop: -170 }}>
        {items.map((it, i) => {
          const p = ease(f, 8 + i * 20, 48 + i * 20, 0, 1);
          return (
            <div key={it.label} style={{ width: 340, textAlign: "center", opacity: ease(f, 4 + i * 20, 28 + i * 20, 0, 1) }}>
              <svg width="340" height="300" viewBox="-110 -110 220 220">{it.draw(p)}</svg>
              <div style={{ fontFamily: BOLD, fontSize: 42, color: INK, marginTop: 4 }}>{it.label}</div>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", bottom: 360, width: "100%", padding: "0 90px" }}>
        <Rise delay={78} size={60} font={LIGHT} color={SOFT}>
          Whatever your smile actually needs.
        </Rise>
      </div>
    </AbsoluteFill></Stage>
  );
};

/* ── 6. end card ─────────────────────────────────────────────────── */
const End: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Stage bg={CREAM} yaw={[-2.5,1.2]} dolly={[-120,28]} dur={150}><Bokeh count={8} tint="#FFFFFF" dur={200} warm /><AbsoluteFill style={{ background: CREAM, justifyContent: "center", alignItems: "center" }}>
      <div style={{
        opacity: ease(f, 2, 30, 0, 1), transform: `scale(${ease(f, 2, 44, 0.94, 1)})`,
        textAlign: "center",
      }}>
        <div style={{ width: 540, height: 540, borderRadius: "50%", overflow: "hidden", margin: "0 auto 50px" }}>
          <Img src={staticFile("logo.jpg")} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        </div>
        <div style={{
          display: "inline-block", background: GOLD, color: "#49351A", fontFamily: BOLD,
          fontSize: 34, letterSpacing: "0.07em", padding: "18px 42px", borderRadius: 44,
          opacity: ease(f, 22, 46, 0, 1),
        }}>COSMETIC CONSULTATIONS</div>
        <div style={{
          marginTop: 26, display: "inline-block", background: BRAND, color: "#fff",
          fontFamily: BOLD, fontSize: 90, padding: "20px 54px", borderRadius: 70,
          opacity: ease(f, 36, 60, 0, 1), transform: `translateY(${ease(f, 36, 60, 14, 0)}px)`,
        }}>(818) 353&#8209;5520</div>
        <div style={{ opacity: ease(f, 52, 78, 0, 1), marginTop: 30 }}>
          <div style={{ fontFamily: BOLD, fontSize: 38, color: INK }}>7902 Foothill Blvd, Sunland</div>
          <div style={{ fontFamily: LIGHT, fontSize: 30, color: SOFT, marginTop: 8 }}>
            English &nbsp;·&nbsp; Espa&ntilde;ol &nbsp;·&nbsp; Farsi
          </div>
          <div style={{ fontFamily: BOLD, fontSize: 38, color: BRAND, marginTop: 14 }}>
            sunlanddentalcare.com
          </div>
        </div>
      </div>
    </AbsoluteFill></Stage>
  );
};


/* ── 30.0s @ 30fps = 900 frames ──────────────────────────────────── */
const T = 18;
export const SunlandCosmetic: React.FC = () => (
  <AbsoluteFill style={{ background: CREAM }}>
    <Fonts />
    <TransitionSeries>
      <TransitionSeries.Sequence durationInFrames={126 + T}><Hook /></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={linearTiming({ durationInFrames: T })} />
      <TransitionSeries.Sequence durationInFrames={144 + T}><ShadeGuide /></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={wipe({ direction: "from-top-left" })} timing={linearTiming({ durationInFrames: T })} />
      <TransitionSeries.Sequence durationInFrames={135 + T}><Since /></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={flip({ direction: "from-right" })} timing={linearTiming({ durationInFrames: T })} />
      <TransitionSeries.Sequence durationInFrames={210 + T}><VeneerBeat /></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={slide({ direction: "from-right" })} timing={linearTiming({ durationInFrames: T })} />
      <TransitionSeries.Sequence durationInFrames={135 + T}><Marks /></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: T })} />
      <TransitionSeries.Sequence durationInFrames={150}><End /></TransitionSeries.Sequence>
    </TransitionSeries>
  </AbsoluteFill>
);
