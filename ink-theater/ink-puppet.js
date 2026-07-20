/*
 * Ink Puppet — plays real motion-capture "clips" (baked by mocap/bvh2clip.mjs)
 * onto a hand-drawn stick figure. Deterministic + seek-safe for HyperFrames.
 *
 * The agent never hand-tunes motion. It just:
 *   var p = InkPuppet.create(mount, {cx, ground});
 *   p.drawIn(tl, {start:0.3});                    // pencil sketches the figure
 *   InkPuppet.choreograph(tl, p, [                // then plays named mocap clips
 *     {clip:'wave', dur:3},
 *     {clip:'twist', dur:3},
 *     {clip:'jump', dur:3.5},
 *     {clip:'walk', dur:4}
 *   ], {start:2.6});
 *
 * Clip names must exist in mocap/catalog.json (unknown names warn + hold).
 *
 * Clips come from window.INK_CLIPS (load clips.js). Motion = professional mocap.
 */
(function (root) {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var GR = "#333";
  function el(tag, a) { var n = document.createElementNS(NS, tag); if (a) for (var k in a) n.setAttribute(k, a[k]); return n; }
  function P(pt) { return (Math.round(pt[0] * 10) / 10) + " " + (Math.round(pt[1] * 10) / 10); }

  var STAND = {
    hips: [0, 0], chest: [0, -88], neck: [0, -150], head: [0, -182],
    shR: [52, -140], elR: [64, -58], haR: [72, 26], shL: [-52, -140], elL: [-64, -58], haL: [-72, 26],
    hipR: [26, -6], knR: [32, 120], ftR: [40, 262], hipL: [-26, -6], knL: [-32, 120], ftL: [-40, 262],
    rootY: 0, groundY: 262
  };

  function create(mount, opts) {
    opts = opts || {};
    var cx = opts.cx != null ? opts.cx : 960, ground = opts.ground != null ? opts.ground : 900;
    var sw = opts.strokeWidth || 6, headR = opts.headR || 46;
    var outer = el("g", {});
    var ink = el("g", opts.boil ? { filter: "url(#" + opts.boil + ")" } : {});
    var head = el("circle", { fill: "none", stroke: GR, "stroke-width": sw });
    function limb() { return el("path", { fill: "none", stroke: GR, "stroke-width": sw, "stroke-linecap": "round", "stroke-linejoin": "round" }); }
    var spine = limb(), armL = limb(), armR = limb(), legL = limb(), legR = limb();
    [spine, armL, armR, legL, legR, head].forEach(function (e) { ink.appendChild(e); });
    outer.appendChild(ink); mount.appendChild(outer);
    var parts = { head: head, spine: spine, armL: armL, armR: armR, legL: legL, legR: legR };
    var pup = {
      outer: outer, ink: ink, parts: parts, cx: cx, ground: ground, headR: headR,
      setPose: function (po) {
        head.setAttribute("cx", po.head[0]); head.setAttribute("cy", po.head[1] - headR * 0.32); head.setAttribute("r", headR);
        spine.setAttribute("d", "M " + P(po.hips) + " L " + P(po.chest) + " L " + P(po.neck) + " L " + P([po.head[0], po.head[1] + headR * 0.5]));
        armR.setAttribute("d", "M " + P(po.shR) + " L " + P(po.elR) + " L " + P(po.haR));
        armL.setAttribute("d", "M " + P(po.shL) + " L " + P(po.elL) + " L " + P(po.haL));
        legR.setAttribute("d", "M " + P(po.hipR) + " L " + P(po.knR) + " L " + P(po.ftR));
        legL.setAttribute("d", "M " + P(po.hipL) + " L " + P(po.knL) + " L " + P(po.ftL));
      },
      place: function (groundY, rootY) { outer.setAttribute("transform", "translate(" + cx + "," + (ground - groundY + (rootY || 0)) + ")"); },
      // pencil sketches the figure limb-by-limb, then holds
      drawIn: function (tl, o) {
        o = o || {}; var t0 = o.start != null ? o.start : 0.3, each = o.each || 0.55;
        pup.setPose(STAND); pup.place(STAND.groundY, 0);
        var seq = [head, spine, armL, armR, legL, legR], done = t0 + seq.length * each * 0.6 + each;
        seq.forEach(function (e, i) {
          var L = e.getTotalLength(); e.style.strokeDasharray = L; e.style.strokeDashoffset = L;
          tl.to(e, { strokeDashoffset: 0, duration: each, ease: "power1.inOut" }, t0 + i * each * 0.6);
        });
        seq.forEach(function (e) { tl.set(e, { strokeDasharray: "none" }, done); });
        pup._revealEnd = done;
        return done;
      }
    };
    pup.setPose(STAND); pup.place(STAND.groundY, 0);
    return pup;
  }

  // Sequence named mocap clips on the timeline. Each clip loops at native fps to
  // fill its duration. Seek-safe: pose is a pure function of the segment's local time.
  function choreograph(tl, pup, segments, opts) {
    opts = opts || {};
    var t = opts.start != null ? opts.start : 0;
    var CLIPS = root.INK_CLIPS || {};
    segments.forEach(function (seg) {
      var clip = CLIPS[seg.clip];
      if (!clip) {
        console.warn('[InkPuppet] unknown clip "' + seg.clip + '" — skipping ' + seg.dur + 's (holds pose). Known clips: ' + Object.keys(CLIPS).join(", "));
        t += seg.dur; return;
      }
      var proxy = { u: 0 };
      tl.to(proxy, {
        u: 1, duration: seg.dur, ease: "none",
        onUpdate: function () {
          var lt = proxy.u * seg.dur;
          var idx = Math.floor(lt * clip.fps);
          idx = seg.loop === false ? Math.min(idx, clip.frames.length - 1) : idx % clip.frames.length;
          var fr = clip.frames[idx];
          pup.setPose(fr);
          pup.place(clip.groundY, fr.rootY || 0);
        }
      }, t);
      t += seg.dur;
    });
    return t;
  }

  root.InkPuppet = { create: create, choreograph: choreograph, STAND: STAND };
})(window);
