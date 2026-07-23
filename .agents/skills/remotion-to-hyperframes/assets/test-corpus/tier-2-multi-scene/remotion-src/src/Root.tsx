import { Composition } from "remotion";
import { MultiScene } from "./MultiScene";

export const RemotionRoot = () => (
  <Composition
    id="MultiScene"
    component={MultiScene}
    durationInFrames={180}
    fps={30}
    width={1280}
    height={720}
  />
);
