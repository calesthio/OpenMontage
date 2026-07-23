import { Composition } from "remotion";
import { z } from "zod";
import { Stargazed, stargazedSchema } from "./Stargazed";

const defaultProps: z.infer<typeof stargazedSchema> = {
  title: "STARGAZED",
  subtitle: "by HeyGen",
  stats: [
    { label: "Stars", value: 1247, color: "#fbbf24" },
    { label: "Forks", value: 312, color: "#60a5fa" },
    { label: "Issues", value: 48, color: "#f87171" },
  ],
  outro: "thanks for watching",
};

export const RemotionRoot = () => (
  <Composition
    id="Stargazed"
    component={Stargazed}
    schema={stargazedSchema}
    durationInFrames={300}
    fps={30}
    width={1280}
    height={720}
    defaultProps={defaultProps}
  />
);
