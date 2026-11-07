import React from "react";
import { Composition, registerRoot } from "remotion";
import { SunlandCosmetic } from "./Cosmetic";

// Own entry point so the stock Root (and its webfont fetches) stay untouched.
const Root: React.FC = () => (
  <Composition
    id="SunlandCosmetic"
    component={SunlandCosmetic}
    durationInFrames={900}
    fps={30}
    width={1080}
    height={1920}
  />
);

registerRoot(Root);
