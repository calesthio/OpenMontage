// T4 case 08 — Multiple blockers + multiple warnings in one file.
//
// Should report:
//   blockers: r2hf/use-state, r2hf/use-effect-deps, r2hf/third-party-react-ui
//   warnings: r2hf/use-callback (also r2hf/delay-render via the import chain
//             would only fire if delayRender is actually called)
//
// Tests that the linter aggregates findings correctly and does not stop at
// the first blocker.

import React, { useState, useEffect, useCallback } from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { Card } from "@chakra-ui/react";

interface Item {
  id: string;
  label: string;
}

export const MixedBlockers: React.FC = () => {
  const frame = useCurrentFrame();
  const [items, setItems] = useState<Item[]>([]);

  useEffect(() => {
    fetch("/api/items")
      .then((r) => r.json())
      .then(setItems);
  }, [frame]);

  const onClick = useCallback(() => {
    setItems((prev) => [...prev, { id: String(prev.length), label: "new" }]);
  }, []);

  return (
    <AbsoluteFill onClick={onClick}>
      {items.map((item) => (
        <Card key={item.id}>{item.label}</Card>
      ))}
    </AbsoluteFill>
  );
};
