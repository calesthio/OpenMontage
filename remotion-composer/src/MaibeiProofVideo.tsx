import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

type Segment = {
  id: string;
  start: number;
  end: number;
  caption: string;
  hot: string[];
};

export type MaibeiProofVideoProps = {
  assetBase: string;
  title: string;
  cta: string;
  durationSeconds: number;
  segments: Segment[];
};

const DEFAULT_SEGMENTS: Segment[] = [
  {
    id: "s01",
    start: 0,
    end: 5.2,
    caption: "AI 重构六一八了，商家别再卡在拍摄排期里。",
    hot: ["六一八"],
  },
  {
    id: "s02",
    start: 5.2,
    end: 11.6,
    caption: "拖慢上新的，是原图不能快速变主图、详情图、场景图和短视频。",
    hot: ["拖慢上新", "主图", "短视频"],
  },
  {
    id: "s03",
    start: 11.6,
    end: 20.2,
    caption: "看格纹半身裙：上传商品图，填套图要求，结果一次出来。",
    hot: ["格纹半身裙", "一次出来"],
  },
  {
    id: "s04",
    start: 20.2,
    end: 28.8,
    caption: "放大看：主体、穿搭关系、材质卖点都留住，才敢上架和投流。",
    hot: ["放大看", "上架", "投流"],
  },
  {
    id: "s05",
    start: 28.8,
    end: 38.6,
    caption: "再看三个功能：换场景做多渠道画面，AI 模特做上身效果，一键生视频做动态素材。",
    hot: ["换场景", "AI 模特", "一键生视频"],
  },
  {
    id: "s06",
    start: 38.6,
    end: 48,
    caption: "所以别只看热闹。六一八后要降本，先补商品图产能。点主页链接，上传一张图试试。",
    hot: ["商品图产能", "上传一张图"],
  },
];

const BLUE = "#2563eb";
const ORANGE = "#ff8a00";
const INK = "#111827";
const CAPTION_BG = "rgba(17, 24, 39, 0.84)";

const secToFrame = (sec: number, fps: number) => Math.round(sec * fps);

const asset = (base: string, name: string) => staticFile(`${base}/${name}`);

const inOut = (
  frame: number,
  start: number,
  end: number,
  fps: number,
  inSec = 0.35,
  outSec = 0.25,
) => {
  const inFrames = inSec * fps;
  const outFrames = outSec * fps;
  const fadeIn = interpolate(frame, [start, start + inFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const fadeOut = interpolate(frame, [end - outFrames, end], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.7, 0, 0.84, 0),
  });
  return Math.min(fadeIn, fadeOut);
};

const rise = (localFrame: number, fps: number, distance = 42) =>
  interpolate(localFrame, [0, 0.5 * fps], [distance, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

const Brand = ({ base }: { base: string }) => (
  <div
    style={{
      position: "absolute",
      top: 42,
      left: 44,
      zIndex: 80,
      display: "flex",
      alignItems: "center",
      gap: 14,
      padding: "13px 18px",
      borderRadius: 999,
      background: "rgba(255,255,255,.9)",
      border: "2px solid rgba(37,99,235,.16)",
      boxShadow: "0 14px 38px rgba(37,99,235,.12)",
    }}
  >
    <Img src={asset(base, "maibei-logo.png")} style={{ height: 38, width: "auto" }} />
    <span style={{ fontWeight: 900, fontSize: 24, color: INK }}>卖倍AI</span>
  </div>
);

const Background = () => (
  <AbsoluteFill
    style={{
      background:
        "radial-gradient(circle at 78% 12%, rgba(37,99,235,.18), transparent 32%), linear-gradient(180deg,#f8fbff 0%,#eef5ff 100%)",
      overflow: "hidden",
    }}
  >
    <div
      style={{
        position: "absolute",
        inset: 0,
        backgroundImage:
          "linear-gradient(rgba(37,99,235,.08) 1px, transparent 1px), linear-gradient(90deg, rgba(37,99,235,.08) 1px, transparent 1px)",
        backgroundSize: "54px 54px",
        opacity: 0.55,
      }}
    />
  </AbsoluteFill>
);

const MediaCard = ({
  children,
  style,
}: {
  children: React.ReactNode;
  style: React.CSSProperties;
}) => (
  <div
    style={{
      position: "absolute",
      overflow: "hidden",
      borderRadius: 32,
      border: "3px solid #d8e3f8",
      background: "white",
      boxShadow: "0 24px 60px rgba(37,99,235,.16)",
      ...style,
    }}
  >
    {children}
  </div>
);

const FitImg = ({ base, name }: { base: string; name: string }) => (
  <Img
    src={asset(base, name)}
    style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
  />
);

const Pill = ({
  children,
  orange = false,
  style,
}: {
  children: React.ReactNode;
  orange?: boolean;
  style?: React.CSSProperties;
}) => (
  <div
    style={{
      position: "absolute",
      zIndex: 50,
      display: "inline-flex",
      alignItems: "center",
      padding: "10px 16px",
      borderRadius: 999,
      color: orange ? INK : "white",
      background: orange ? ORANGE : BLUE,
      fontWeight: 950,
      fontSize: 24,
      ...style,
    }}
  >
    {children}
  </div>
);

const Caption = ({ segment }: { segment: Segment }) => {
  const parts = segment.hot.reduce<React.ReactNode[]>((acc, hot) => {
    const next: React.ReactNode[] = [];
    for (const item of acc.length ? acc : [segment.caption]) {
      if (typeof item !== "string") {
        next.push(item);
        continue;
      }
      const split = item.split(hot);
      split.forEach((chunk, index) => {
        if (chunk) next.push(chunk);
        if (index < split.length - 1) {
          next.push(
            <span key={`${hot}-${index}`} style={{ color: ORANGE, fontSize: 60 }}>
              {hot}
            </span>,
          );
        }
      });
    }
    return next;
  }, []);

  return (
    <div
      style={{
        position: "absolute",
        left: 54,
        right: 54,
        bottom: segment.id === "s06" ? 68 : 82,
        zIndex: 90,
        padding: "18px 22px",
        borderRadius: 26,
        background: CAPTION_BG,
        boxShadow: "0 18px 44px rgba(17,24,39,.2)",
        color: "white",
        fontSize: 48,
        lineHeight: 1.22,
        fontWeight: 950,
        textShadow: "0 3px 0 #111827, 0 0 18px rgba(17,24,39,.42)",
      }}
    >
      {parts}
    </div>
  );
};

const Scene = ({
  start,
  end,
  children,
}: {
  start: number;
  end: number;
  children: (localFrame: number) => React.ReactNode;
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const startFrame = secToFrame(start, fps);
  const endFrame = secToFrame(end, fps);
  const opacity = inOut(frame, startFrame, endFrame, fps);
  const localFrame = frame - startFrame;
  return (
    <Sequence
      from={startFrame}
      durationInFrames={endFrame - startFrame}
      layout="none"
    >
      <AbsoluteFill style={{ opacity }}>{children(localFrame)}</AbsoluteFill>
    </Sequence>
  );
};

const ResultPanel = ({ base }: { base: string }) => (
  <div
    style={{
      position: "absolute",
      right: 88,
      top: 370,
      width: 455,
      height: 610,
      zIndex: 40,
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gridTemplateRows: "auto 1fr 1fr",
      gap: 14,
      padding: 18,
      borderRadius: 30,
      background: "rgba(255,255,255,.94)",
      border: "3px solid rgba(37,99,235,.18)",
      boxShadow: "0 20px 54px rgba(37,99,235,.18)",
    }}
  >
    <div
      style={{
        gridColumn: "1 / -1",
        fontSize: 28,
        fontWeight: 950,
        color: BLUE,
      }}
    >
      同一商品生成结果
    </div>
    {["set-output-1.jpg", "set-output-2.jpg", "set-output-3.jpg", "set-input-1.jpg"].map(
      (name) => (
        <div key={name} style={{ overflow: "hidden", borderRadius: 20, border: "2px solid #d8e3f8" }}>
          <FitImg base={base} name={name} />
        </div>
      ),
    )}
  </div>
);

export const MaibeiProofVideo: React.FC<MaibeiProofVideoProps> = ({
  assetBase,
  title,
  cta,
  durationSeconds,
  segments = DEFAULT_SEGMENTS,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const activeSegment =
    segments.find((s) => frame >= secToFrame(s.start, fps) && frame < secToFrame(s.end, fps)) ||
    segments[segments.length - 1];
  const slowPush = interpolate(frame, [0, durationSeconds * fps], [1, 1.018], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", Arial, sans-serif' }}>
      <Background />
      <Brand base={assetBase} />

      <Scene start={0} end={5.2}>
        {(localFrame) => (
          <>
            <div
              style={{
                position: "absolute",
                top: 136 + rise(localFrame, fps, 26),
                left: 54,
                fontSize: 28,
                fontWeight: 950,
                color: BLUE,
              }}
            >
              商品图产能，不是热点热闹
            </div>
            <div
              style={{
                position: "absolute",
                top: 176 + rise(localFrame, fps, 42),
                left: 54,
                right: 54,
                fontSize: 72,
                lineHeight: 1.04,
                fontWeight: 950,
                color: INK,
              }}
            >
              一张商品图
              <br />
              直接变成一套上新素材
            </div>
            <MediaCard style={{ left: 54, top: 392, width: 372, height: 520 }}>
              <FitImg base={assetBase} name="set-input-1.jpg" />
            </MediaCard>
            <MediaCard style={{ left: 90, top: 840, width: 292, height: 404 }}>
              <FitImg base={assetBase} name="set-input-2.png" />
            </MediaCard>
            <MediaCard style={{ right: 54, top: 350, width: 458, height: 480 }}>
              <FitImg base={assetBase} name="set-output-1.jpg" />
            </MediaCard>
            <MediaCard style={{ right: 54, top: 842, width: 218, height: 318 }}>
              <FitImg base={assetBase} name="set-output-2.jpg" />
            </MediaCard>
            <MediaCard style={{ right: 294, top: 842, width: 218, height: 318 }}>
              <FitImg base={assetBase} name="set-output-3.jpg" />
            </MediaCard>
            <Pill orange style={{ left: 70, top: 350 }}>生成前</Pill>
            <Pill style={{ right: 76, top: 308 }}>生成后</Pill>
          </>
        )}
      </Scene>

      <Scene start={5.2} end={11.6}>
        {() => (
          <>
            <div style={{ position: "absolute", top: 178, left: 54, fontSize: 64, lineHeight: 1.08, fontWeight: 950 }}>
              拖慢上新的
              <br />
              不是不会追热点
            </div>
            <div
              style={{
                position: "absolute",
                left: 64,
                top: 392,
                width: 952,
                height: 960,
                borderRadius: 38,
                overflow: "hidden",
                border: "3px solid rgba(37,99,235,.18)",
                transform: `scale(${slowPush})`,
                transformOrigin: "center",
              }}
            >
              <OffthreadVideo
                src={asset(assetBase, "set-recording-normalized.mp4")}
                startFrom={secToFrame(1.8, fps)}
                muted
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            </div>
            {["设计排队", "投流缺素材", "改图太慢"].map((label, index) => (
              <div
                key={label}
                style={{
                  position: "absolute",
                  left: 70 + index * 170,
                  top: 1398,
                  padding: "11px 18px",
                  borderRadius: 999,
                  background: "white",
                  color: INK,
                  border: `3px solid ${BLUE}`,
                  fontSize: 25,
                  fontWeight: 950,
                }}
              >
                {label}
              </div>
            ))}
          </>
        )}
      </Scene>

      <Scene start={11.6} end={20.2}>
        {() => (
          <>
            <Pill style={{ left: 70, top: 214 }}>真实操作链路</Pill>
            <div
              style={{
                position: "absolute",
                left: 64,
                top: 270,
                width: 952,
                height: 1190,
                borderRadius: 38,
                overflow: "hidden",
                border: "3px solid rgba(37,99,235,.18)",
              }}
            >
              <OffthreadVideo
                src={asset(assetBase, "set-recording-normalized.mp4")}
                startFrom={secToFrame(1.0, fps)}
                muted
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            </div>
            <ResultPanel base={assetBase} />
          </>
        )}
      </Scene>

      <Scene start={20.2} end={28.8}>
        {(localFrame) => {
          const zoom = interpolate(localFrame, [0, 8.6 * fps], [1, 1.07], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          });
          return (
            <>
              <div style={{ position: "absolute", top: 156, left: 54, fontSize: 60, fontWeight: 950 }}>
                放大看，能不能真的上架
              </div>
              <MediaCard style={{ left: 66, top: 286, width: 948, height: 760 }}>
                <div style={{ width: "100%", height: "100%", transform: `scale(${zoom})` }}>
                  <FitImg base={assetBase} name="set-output-1.jpg" />
                </div>
              </MediaCard>
              <MediaCard style={{ left: 66, top: 1088, width: 456, height: 386 }}>
                <FitImg base={assetBase} name="set-output-2.jpg" />
              </MediaCard>
              <MediaCard style={{ right: 66, top: 1088, width: 456, height: 386 }}>
                <FitImg base={assetBase} name="set-output-3.jpg" />
              </MediaCard>
              <Pill orange style={{ left: 86, top: 1050 }}>局部检查</Pill>
            </>
          );
        }}
      </Scene>

      <Scene start={28.8} end={38.6}>
        {(localFrame) => {
          const y = interpolate(localFrame, [0, 6 * fps], [0, -18], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.45, 0, 0.55, 1),
          });
          return (
            <>
              <div style={{ position: "absolute", top: 150, left: 54, right: 54, fontSize: 58, fontWeight: 950 }}>
                不止套图，再补三种素材能力
              </div>
              <MediaCard style={{ left: 54, top: 382 + y, width: 306, height: 720 }}>
                <FitImg base={assetBase} name="scene-output.jpg" />
                <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, padding: "18px 14px", color: "white", background: INK, fontSize: 28, fontWeight: 950 }}>换场景</div>
              </MediaCard>
              <MediaCard style={{ left: 386, top: 382 + y, width: 306, height: 720 }}>
                <FitImg base={assetBase} name="tryon-output.jpg" />
                <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, padding: "18px 14px", color: "white", background: INK, fontSize: 28, fontWeight: 950 }}>AI 模特</div>
              </MediaCard>
              <MediaCard style={{ right: 54, top: 382 + y, width: 306, height: 720 }}>
                <OffthreadVideo
                  src={asset(assetBase, "bb-video-output-normalized.mp4")}
                  muted
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              </MediaCard>
              <Pill style={{ right: 70, top: 1068 }}>一键生视频</Pill>
            </>
          );
        }}
      </Scene>

      <Scene start={38.6} end={48}>
        {(localFrame) => {
          const pulse = interpolate(localFrame % 36, [0, 18, 36], [1, 1.04, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.45, 0, 0.55, 1),
          });
          return (
            <>
              <div
                style={{
                  position: "absolute",
                  left: 62,
                  right: 62,
                  top: 460,
                  minHeight: 650,
                  borderRadius: 44,
                  background: INK,
                  color: "white",
                  padding: 56,
                  boxShadow: "0 34px 80px rgba(17,24,39,.22)",
                }}
              >
                <div style={{ fontSize: 74, lineHeight: 1.08, fontWeight: 950 }}>
                  别只看热闹
                  <br />
                  先补商品图产能
                </div>
              </div>
              <div
                style={{
                  position: "absolute",
                  left: 112,
                  right: 112,
                  top: 1148,
                  padding: 30,
                  borderRadius: 999,
                  background: ORANGE,
                  color: INK,
                  fontSize: 46,
                  textAlign: "center",
                  fontWeight: 950,
                  transform: `scale(${pulse})`,
                  boxShadow: "0 24px 52px rgba(255,138,0,.32)",
                }}
              >
                {cta}
              </div>
              <div style={{ position: "absolute", left: 92, right: 92, top: 1320, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 18 }}>
                {["set-output-1.jpg", "scene-output.jpg", "tryon-output.jpg"].map((name) => (
                  <div key={name} style={{ height: 230, overflow: "hidden", borderRadius: 24, border: "3px solid #d8e3f8", boxShadow: "0 18px 42px rgba(37,99,235,.16)" }}>
                    <FitImg base={assetBase} name={name} />
                  </div>
                ))}
              </div>
            </>
          );
        }}
      </Scene>

      <Caption segment={activeSegment} />
      <Audio src={asset(assetBase, "narration.wav")} />
    </AbsoluteFill>
  );
};

export const defaultMaibeiProofVideoProps: MaibeiProofVideoProps = {
  assetBase: "maibei-openmontage-handoff-proof",
  title: "AI 已经重构 618 了，商家还卡在商品图拍摄排期里",
  cta: "上传一张商品图，先跑一套上新素材",
  durationSeconds: 48,
  segments: DEFAULT_SEGMENTS,
};
