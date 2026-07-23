import { AbsoluteFill, Sequence } from "remotion";
import { z } from "zod";
import { TitleScene } from "./scenes/TitleScene";
import { StatsScene } from "./scenes/StatsScene";
import { OutroScene } from "./scenes/OutroScene";

export const stargazedSchema = z.object({
  title: z.string(),
  subtitle: z.string(),
  stats: z.array(
    z.object({
      label: z.string(),
      value: z.number(),
      color: z.string(),
    }),
  ),
  outro: z.string(),
});

export const Stargazed: React.FC<z.infer<typeof stargazedSchema>> = ({
  title,
  subtitle,
  stats,
  outro,
}) => (
  <AbsoluteFill style={{ backgroundColor: "#0a0a0a" }}>
    <Sequence from={0} durationInFrames={90}>
      <TitleScene title={title} subtitle={subtitle} />
    </Sequence>
    <Sequence from={90} durationInFrames={120}>
      <StatsScene stats={stats} />
    </Sequence>
    <Sequence from={210} durationInFrames={90}>
      <OutroScene text={outro} />
    </Sequence>
  </AbsoluteFill>
);
