---
name: canvas-procedural-animation
description: Use p5.js/canvas for local procedural character effects: particles, weather, squash/stretch, walk cycles, and environmental motion.
license: MIT
---

# Canvas Procedural Animation

Use this skill when p5.js or Canvas is used for character-supporting motion:
rain, snow, leaves, feathers, ambient particles, squash/stretch, or procedural
walk cycles.

## Proven Pattern

p5.js runs setup once and redraws continuously through `draw()`. Keep animation
state deterministic from time/frame values when rendering previews.

```js
function setup() {
  createCanvas(1920, 1080);
}

function draw() {
  const t = millis() / 1000;
  clear();
  drawCharacter(width / 2, height / 2 + sin(t * 8) * 8);
}
```

## Use For

- Particle/weather overlays.
- Environmental motion.
- Simple procedural bodies.
- Effects that do not need individually authored SVG parts.

## Avoid For

- Complex facial acting where SVG/layered rig parts are easier to inspect.
- Final renders that need exact frame determinism unless the runtime exposes
  frame-index control.

## Sources

- p5.js `setup()` reference: https://p5js.org/reference/p5/setup/
- p5.js `draw()` reference: https://p5js.org/reference/p5/draw/
- p5.js animation examples: https://p5js.org/examples/
