/*
 * Ink Theater — a deterministic, seek-safe engine for hand-drawn "moving art".
 * Browser global `InkTheater`. Designed for HyperFrames: every primitive is a pure
 * function of geometry or of the GSAP timeline playhead, so frame N is reproducible
 * from time alone. No render-time clocks, no Math.random at runtime.
 *
 * Modules:
 *   rng / noise      — seeded determinism
 *   inkPath/inkRibbon — hand-drawn variable-width strokes (the "look")
 *   boil             — seek-safe stepped line-boil driven off the timeline
 *   springEase / ease — closed-form damped-spring eases (anticipation/overshoot/settle)
 *   fabrik           — 2D inverse kinematics for limb rigs
 *   parts            — parametric, composable low-tech contraption pieces (the grammar)
 *   mascot           — a riggable deadpan ink character
 */
(function (root) {
  "use strict";
  var SVGNS = "http://www.w3.org/2000/svg";

  // ---- DOM helper ------------------------------------------------------------
  function el(tag, attrs, kids) {
    var n = document.createElementNS(SVGNS, tag);
    if (attrs) for (var k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    if (kids) (Array.isArray(kids) ? kids : [kids]).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }

  // ---- Seeded determinism ----------------------------------------------------
  function rng(seed) {            // mulberry32
    var a = (seed >>> 0) || 1;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ---- Path math -------------------------------------------------------------
  function resample(pts, step) {
    if (pts.length < 2) return pts.slice();
    var out = [pts[0]], acc = 0, i, prev = pts[0];
    for (i = 1; i < pts.length; i++) {
      var p = pts[i], dx = p[0] - prev[0], dy = p[1] - prev[1], d = Math.hypot(dx, dy);
      while (acc + d >= step) {
        var t = (step - acc) / d;
        prev = [prev[0] + dx * t, prev[1] + dy * t];
        out.push(prev);
        dx = p[0] - prev[0]; dy = p[1] - prev[1]; d = Math.hypot(dx, dy); acc = 0;
      }
      acc += d; prev = p;
    }
    out.push(pts[pts.length - 1]);
    return out;
  }
  function normals(pts) {
    var ns = [], i;
    for (i = 0; i < pts.length; i++) {
      var a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
      var tx = b[0] - a[0], ty = b[1] - a[1], L = Math.hypot(tx, ty) || 1;
      ns.push([-ty / L, tx / L]);
    }
    return ns;
  }
  // Catmull-Rom -> cubic Bézier 'd' (smooth curve through points)
  function smoothD(pts, closed) {
    if (pts.length < 2) return "";
    var d = "M" + r2(pts[0][0]) + " " + r2(pts[0][1]), i, n = pts.length;
    for (i = 0; i < n - 1; i++) {
      var p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      var c1x = p1[0] + (p2[0] - p0[0]) / 6, c1y = p1[1] + (p2[1] - p0[1]) / 6;
      var c2x = p2[0] - (p3[0] - p1[0]) / 6, c2y = p2[1] - (p3[1] - p1[1]) / 6;
      d += "C" + r2(c1x) + " " + r2(c1y) + " " + r2(c2x) + " " + r2(c2y) + " " + r2(p2[0]) + " " + r2(p2[1]);
    }
    return d + (closed ? "Z" : "");
  }
  function r2(x) { return Math.round(x * 100) / 100; }

  // Bake a small deterministic hand-wobble into a polyline (perpendicular jitter).
  function wobblePts(pts, amp, seed) {
    var rand = rng(seed || 1), ns = normals(pts);
    return pts.map(function (p, i) {
      var j = (rand() - 0.5) * 2 * amp;
      return [p[0] + ns[i][0] * j, p[1] + ns[i][1] * j];
    });
  }

  // A confident hand-drawn centerline (use with stroke + round caps).
  function inkPath(pts, opt) {
    opt = opt || {};
    var P = wobblePts(resample(pts, opt.step || 26), opt.wobble != null ? opt.wobble : 1.6, opt.seed || 7);
    return smoothD(P, opt.closed);
  }

  // A variable-width brush ribbon (returns a CLOSED outline, fill it black).
  // Width tapers at the ends and swells in the middle — the difference between
  // a drawn line and a traced one.
  function inkRibbon(pts, opt) {
    opt = opt || {};
    var w = opt.width || 12, taper = opt.taper != null ? opt.taper : 0.55, seed = opt.seed || 5;
    var P = wobblePts(resample(pts, opt.step || 22), opt.wobble != null ? opt.wobble : 1.2, seed);
    var ns = normals(P), n = P.length, rand = rng(seed + 99);
    var left = [], right = [], i;
    for (i = 0; i < n; i++) {
      var t = n > 1 ? i / (n - 1) : 0;
      // width profile: 0 at ends, 1 in the belly; taper controls end thinness
      var prof = Math.pow(Math.sin(Math.PI * t), taper) * (0.85 + 0.3 * rand());
      var hw = (w / 2) * prof + 0.6;
      left.push([P[i][0] + ns[i][0] * hw, P[i][1] + ns[i][1] * hw]);
      right.push([P[i][0] - ns[i][0] * hw, P[i][1] - ns[i][1] * hw]);
    }
    return smoothD(left, false) + " " + smoothD(right.reverse(), false).replace(/^M/, "L") + "Z";
  }

  // ---- Seek-safe line boil ---------------------------------------------------
  // Steps a feTurbulence seed across the timeline so the inked lines "boil" at a
  // low frame-rate (hand-drawn feel) while staying 100% deterministic under seek.
  function boil(turbulenceEl, tl, opt) {
    opt = opt || {};
    var dur = opt.duration || tl.duration() || 8;
    var fps = opt.fps || 9;
    var steps = Math.max(1, Math.round(dur * fps));
    tl.to(turbulenceEl, { attr: { seed: steps }, duration: dur, ease: "steps(" + steps + ")" }, 0);
    return turbulenceEl;
  }

  // ---- Closed-form damped spring eases --------------------------------------
  // Step response of a damped harmonic oscillator, normalized to settle at 1.
  // Underdamped => overshoot + settle (the juicy follow-through). Pure fn of p.
  function springEase(opt) {
    opt = opt || {};
    var stiffness = opt.stiffness || 170, damping = opt.damping || 14, mass = opt.mass || 1;
    var w = Math.sqrt(stiffness / mass);              // natural angular frequency
    var zeta = damping / (2 * Math.sqrt(stiffness * mass)); // damping ratio
    var horizon = opt.horizon || 1;                   // p maps to t in [0, horizon*settle]
    // choose a time-scale so motion is essentially settled at p=1
    var settle = 8 / (zeta * w || 1);
    function y(t) {
      if (zeta < 1) {
        var wd = w * Math.sqrt(1 - zeta * zeta);
        return 1 - Math.exp(-zeta * w * t) * (Math.cos(wd * t) + (zeta * w / wd) * Math.sin(wd * t));
      } else if (zeta === 1) {
        return 1 - Math.exp(-w * t) * (1 + w * t);
      } else {
        var a = -w * (zeta - Math.sqrt(zeta * zeta - 1)), b = -w * (zeta + Math.sqrt(zeta * zeta - 1));
        var A = b / (b - a), B = -a / (b - a);
        return 1 - (A * Math.exp(a * t) + B * Math.exp(b * t));
      }
    }
    var f = function (p) {
      if (p <= 0) return 0; if (p >= 1) return 1;     // pin endpoints
      return y(p * settle * horizon);
    };
    return f;
  }
  var ease = {
    settle: springEase({ stiffness: 180, damping: 18 }),   // minimal overshoot
    overshoot: springEase({ stiffness: 200, damping: 11 }),// clear overshoot + settle
    bouncy: springEase({ stiffness: 260, damping: 8 }),    // springy
    soft: springEase({ stiffness: 120, damping: 20 })      // gentle, no overshoot
  };

  // ---- FABRIK 2D inverse kinematics -----------------------------------------
  // lengths: array of segment lengths (n segments -> n+1 joints). Returns joint pts.
  function fabrik(lengths, origin, target, opt) {
    opt = opt || {};
    var iters = opt.iterations || 12, tol = opt.tol || 0.4;
    var n = lengths.length, total = lengths.reduce(function (a, b) { return a + b; }, 0);
    var pts = [origin.slice()], i;
    for (i = 0; i < n; i++) pts.push([origin[0] + lengths[i] * (i + 1), origin[1]]); // seed straight
    var dist = Math.hypot(target[0] - origin[0], target[1] - origin[1]);
    if (dist > total) {                                // unreachable: stretch straight
      var ux = (target[0] - origin[0]) / dist, uy = (target[1] - origin[1]) / dist, acc = origin.slice();
      pts[0] = origin.slice();
      for (i = 0; i < n; i++) { acc = [acc[0] + ux * lengths[i], acc[1] + uy * lengths[i]]; pts[i + 1] = acc.slice(); }
      return pts;
    }
    for (var it = 0; it < iters; it++) {
      pts[n] = target.slice();                         // backward
      for (i = n - 1; i >= 0; i--) pts[i] = lerpTo(pts[i + 1], pts[i], lengths[i]);
      pts[0] = origin.slice();                          // forward
      for (i = 0; i < n; i++) pts[i + 1] = lerpTo(pts[i], pts[i + 1], lengths[i]);
      if (Math.hypot(pts[n][0] - target[0], pts[n][1] - target[1]) < tol) break;
    }
    return pts;
  }
  function lerpTo(from, to, len) {
    var dx = to[0] - from[0], dy = to[1] - from[1], d = Math.hypot(dx, dy) || 1;
    return [from[0] + dx / d * len, from[1] + dy / d * len];
  }

  // ---- Contraption grammar — parametric composable parts --------------------
  // Each returns { g: <g>, ... } with named handles the author wires to motion.
  var INK = "#1a1a1a";
  function strokeEl(d, sw) { return el("path", { d: d, fill: "none", stroke: INK, "stroke-width": sw || 4, "stroke-linecap": "round", "stroke-linejoin": "round" }); }
  var parts = {
    // crank wheel with a handle on the rim — spin the returned `wheel` group
    crank: function (cx, cy, r) {
      var wheel = el("g", { transform: "" });
      wheel.appendChild(el("circle", { cx: cx, cy: cy, r: r, fill: "#fff", stroke: INK, "stroke-width": 4 }));
      wheel.appendChild(el("line", { x1: cx, y1: cy, x2: cx, y2: cy - r + 4, stroke: INK, "stroke-width": 2.4 }));
      wheel.appendChild(el("circle", { cx: cx, cy: cy - r + 8, r: r * 0.16, fill: INK })); // handle
      var g = el("g", null, [wheel, el("circle", { cx: cx, cy: cy, r: 3, fill: INK })]);
      return { g: g, wheel: wheel, pivot: [cx, cy] };
    },
    // gauge with a needle — swing `needle` (pivot at center)
    gauge: function (cx, cy, r) {
      var needle = el("line", { x1: cx, y1: cy, x2: cx, y2: cy - r + 6, stroke: INK, "stroke-width": 4 });
      var g = el("g", null, [
        el("circle", { cx: cx, cy: cy, r: r, fill: "#fff", stroke: INK, "stroke-width": 4 }),
        strokeEl("M" + (cx - r * 0.7) + " " + (cy - r * 0.2) + " A " + (r * 0.7) + " " + (r * 0.7) + " 0 0 1 " + (cx + r * 0.7) + " " + (cy - r * 0.2), 2),
        needle, el("circle", { cx: cx, cy: cy, r: 3.5, fill: INK })
      ]);
      return { g: g, needle: needle, pivot: [cx, cy] };
    },
    hopper: function (cx, topY, mouthW, depth) {
      var hw = mouthW / 2;
      return { g: strokeEl("M" + (cx - hw * 0.5) + " " + (topY + depth) + " L" + (cx - hw) + " " + topY + " L" + (cx + hw) + " " + topY + " L" + (cx + hw * 0.5) + " " + (topY + depth)), mouth: [cx, topY] };
    },
    slot: function (x, y, w, h) { return { g: el("rect", { x: x, y: y, width: w, height: h, rx: 2, fill: INK }), out: [x + w, y + h / 2] }; },
    lever: function (cx, cy, len) {
      var arm = el("line", { x1: cx, y1: cy, x2: cx + len, y2: cy - len * 0.2, stroke: INK, "stroke-width": 6, "stroke-linecap": "round" });
      var knob = el("circle", { cx: cx + len, cy: cy - len * 0.2, r: 9, fill: INK });
      return { g: el("g", null, [el("circle", { cx: cx, cy: cy, r: 5, fill: INK }), arm, knob]), arm: arm, knob: knob, pivot: [cx, cy] };
    },
    box: function (x, y, w, h, label) {
      var g = el("g", null, [el("rect", { x: x, y: y, width: w, height: h, rx: 6, fill: "#fff", stroke: INK, "stroke-width": 4 })]);
      if (label) { var t = el("text", { x: x + w / 2, y: y + h / 2 + 6, "text-anchor": "middle", fill: INK, "font-size": 22, "font-family": "Caveat, cursive" }); t.textContent = label; g.appendChild(t); }
      return { g: g };
    }
  };

  // ---- Mascot ----------------------------------------------------------------
  // A deadpan ink blob with two FABRIK-posable arms.
  function mascot(opt) {
    opt = opt || {};
    var x = opt.x || 0, y = opt.y || 0, s = opt.scale || 1;
    var bw = 40 * s, bh = 50 * s;
    var body = el("ellipse", { cx: x, cy: y, rx: bw, ry: bh, fill: INK });
    var legL = el("path", { d: "M" + (x - 12 * s) + " " + (y + bh * 0.92) + " l" + (-4 * s) + " " + (24 * s), stroke: INK, "stroke-width": 7 * s, fill: "none", "stroke-linecap": "round" });
    var legR = el("path", { d: "M" + (x + 12 * s) + " " + (y + bh * 0.92) + " l" + (4 * s) + " " + (24 * s), stroke: INK, "stroke-width": 7 * s, fill: "none", "stroke-linecap": "round" });
    var eyeL = el("circle", { cx: x - 12 * s, cy: y - 16 * s, r: 7 * s, fill: "#fff" });
    var eyeR = el("circle", { cx: x + 12 * s, cy: y - 16 * s, r: 7 * s, fill: "#fff" });
    var armL = el("path", { d: "", stroke: INK, "stroke-width": 7 * s, fill: "none", "stroke-linecap": "round", "stroke-linejoin": "round" });
    var armR = el("path", { d: "", stroke: INK, "stroke-width": 7 * s, fill: "none", "stroke-linecap": "round", "stroke-linejoin": "round" });
    var shoulderL = [x - bw * 0.7, y - 2 * s], shoulderR = [x + bw * 0.7, y - 2 * s];
    var seg = [32 * s, 30 * s];
    function poseArm(pathEl, shoulder, target) {
      var j = fabrik(seg, shoulder, target);
      pathEl.setAttribute("d", "M" + r2(j[0][0]) + " " + r2(j[0][1]) + " L" + r2(j[1][0]) + " " + r2(j[1][1]) + " L" + r2(j[2][0]) + " " + r2(j[2][1]));
    }
    poseArm(armL, shoulderL, [shoulderL[0] - 18 * s, shoulderL[1] + 30 * s]);
    poseArm(armR, shoulderR, [shoulderR[0] + 18 * s, shoulderR[1] + 30 * s]);
    var g = el("g", null, [armL, armR, body, legL, legR, eyeL, eyeR]);
    return {
      g: g, body: body, eyeL: eyeL, eyeR: eyeR, armL: armL, armR: armR,
      origin: [x, y], shoulderL: shoulderL, shoulderR: shoulderR,
      reachL: function (t) { poseArm(armL, shoulderL, t); },
      reachR: function (t) { poseArm(armR, shoulderR, t); }
    };
  }

  // ---- comic speech balloon (the "characters talking" primitive) ----
  // Builds an ink bubble + tail (grows from the mouth) and an HTML overlay text,
  // and animates it on the timeline. Text is HTML so the webfont applies.
  //   balloon(tl, { into:<g>, overlay:<div>, at, dur, text, mouth:[x,y],
  //                 center:[x,y], w, size, font, boil })
  function balloon(tl, o) {
    o = o || {};
    var g = root.gsap;
    var bx = (o.center && o.center[0]) || 1030, by = (o.center && o.center[1]) || 320;
    var w = o.w || Math.max(200, String(o.text || "").length * 26), h = o.h || 116;
    var mouth = o.mouth || [bx - 260, by + 130];
    var grp = el("g", o.boil ? { filter: "url(#" + o.boil + ")" } : {});
    grp.appendChild(el("rect", { x: bx - w / 2, y: by - h / 2, width: w, height: h, rx: h / 2, fill: "#fff", stroke: INK, "stroke-width": 3.4 }));
    grp.appendChild(el("path", { d: "M " + (bx - 40) + " " + (by + h / 2 - 6) + " L " + mouth[0] + " " + mouth[1] + " L " + (bx - 4) + " " + (by + h / 2 - 2) + " Z", fill: "#fff", stroke: INK, "stroke-width": 3.4, "stroke-linejoin": "round" }));
    (o.into || document.body).appendChild(grp);
    var d = document.createElement("div");
    d.textContent = o.text;
    d.style.cssText = "position:absolute;display:flex;align-items:center;justify-content:center;text-align:center;opacity:0;color:" + INK +
      ";font-family:'" + (o.font || "InkHand") + "',cursive;left:" + (bx - w / 2) + "px;top:" + (by - h / 2) + "px;width:" + w + "px;height:" + h + "px;font-size:" + (o.size || 50) + "px";
    (o.overlay || document.body).appendChild(d);
    if (tl && g) {
      g.set(grp, { svgOrigin: mouth[0] + " " + mouth[1], scale: 0 });
      tl.to(grp, { scale: 1, duration: 0.4, ease: ease.overshoot }, o.at || 0);
      tl.to(d, { opacity: 1, duration: 0.25 }, (o.at || 0) + 0.18);
      tl.to([grp, d], { opacity: 0, duration: 0.3 }, (o.at || 0) + (o.dur || 2) - 0.3);
    }
    return { group: grp, text: d };
  }

  root.InkTheater = {
    el: el, rng: rng, resample: resample, smoothD: smoothD, wobblePts: wobblePts,
    inkPath: inkPath, inkRibbon: inkRibbon, boil: boil,
    springEase: springEase, ease: ease, fabrik: fabrik,
    parts: parts, mascot: mascot, balloon: balloon, INK: INK
  };
})(window);
