import React, { useState, useEffect, useLayoutEffect } from "react";
import { useCurrentFrame, AbsoluteFill, delayRender, continueRender } from "remotion";
import { Button } from "@mui/material";

// Custom hook in `export const useFoo = ...` form — earlier custom-hook
// regex anchored to `^\s*(?:function|const|let)` and missed the `export`
// prefix. This covers the regression.
export const useFadeMixed = (n: number) => {
  const f = useCurrentFrame();
  return f / n;
};

export const BadComposition: React.FC = () => {
  const frame = useCurrentFrame();
  const [data, setData] = useState<string | null>(null);
  const [handle] = useState(() => delayRender());

  // Multi-line useEffect body with commas inside (fillRect args) — regression
  // coverage for r2hf/use-effect-deps. An earlier regex `[^,]+` would stop at
  // the first comma inside the body and miss the deps array entirely.
  useEffect(() => {
    fetch("/api/data")
      .then((r) => r.json())
      .then((d) => {
        const ctx = document.createElement("canvas").getContext("2d");
        ctx?.fillRect(0, 0, 100, 100);
        setData(d.text);
        continueRender(handle);
      });
  }, [handle]);

  // Expression-bodied useEffect — the form `useEffect(() => fetch(...), [deps])`
  // has no closing `}`, which an earlier regex anchored on. This and the
  // useLayoutEffect below cover the false-negative cases Miguel surfaced.
  useEffect(() => fetch("/api/heartbeat"), [frame]);
  useLayoutEffect(() => (document.title = `frame ${frame}`), [frame]);

  return (
    <AbsoluteFill>
      <Button>{data ?? "loading"}</Button>
      <span>{frame}</span>
    </AbsoluteFill>
  );
};

export const calculateMetadata = async () => {
  const res = await fetch("/api/duration");
  const { duration } = await res.json();
  return { durationInFrames: duration };
};
