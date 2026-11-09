"""Reel builder — one pipeline for cut-from-footage highlight reels.

Consolidates the per-project ``build_picture`` / ``assemble`` / ``build_audio`` /
``build_delivery`` scripts into a single tool driven by a *reel spec*: a JSON
document holding every project-specific value (paths, grade, stabilisation set,
ambience sources, music dips, deliverables). The code here is generic — pointing
the spec at a different match produces a different reel with no code edits.

Stages, in order:

``picture``   cut each entry of the cutlist out of the source footage: centre
              crop from the native frame, optional stabilisation, grade, scale
              to the delivery profile. Pulls each cut's own audio when the beat
              is marked ``live``.
``assemble``  concat cuts losslessly into blocks, then chain the blocks with
              xfade transitions into a silent picture master.
``audio``     build the ambience bed, the live-sound track, low-end impacts on
              measured roar onsets, the voiceover track and the music bed, then
              mix them through a three-stage sidechain so narration always wins.
``deliver``   mux a graphics render against each mix into the final files.

Every stage is resumable: existing outputs are skipped unless ``force`` is set.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ResumeSupport,
    RetryPolicy,
    ToolResult,
    ToolStability,
    ToolTier,
)

STAGES = ("picture", "assemble", "audio", "deliver")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _run(cmd: list[str], label: str, log: list[str], cwd: Optional[str] = None) -> bool:
    """Run a command, record a one-line outcome, return success."""
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    ok = r.returncode == 0
    log.append(("OK   " if ok else "FAIL ") + label + ("" if ok else "  " + (r.stderr or "")[:240]))
    return ok


def _probe_duration(path: str) -> Optional[float]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True,
    ).stdout.strip()
    try:
        return float(out)
    except (TypeError, ValueError):
        return None


def _even(value: float) -> int:
    """Round to an even integer — libx264 rejects odd dimensions in yuv420p."""
    return int(round(value / 2) * 2)


def _dip_expr(dips: list[Any], depth: float, edge: float) -> str:
    """An ffmpeg volume expression that dips through each (start, end) window.

    Used to ride the music fader under passages where sidechain ducking alone is
    not enough — a long narration block, or a beat that must stay quiet.
    """
    if not dips:
        return "volume=1.0"
    terms = "+".join(
        f"min(1,max(0,(t-{float(a):.2f})/{edge}))*min(1,max(0,({float(b):.2f}-t)/{edge}))"
        for a, b in dips
    )
    return f"volume='1-{depth}*({terms})':eval=frame"


class ReelSpec:
    """A reel spec with defaults applied and paths resolved against the project."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw
        self.project_dir = Path(raw["project_dir"])
        self.source_dir = Path(raw["source_dir"])
        self.variant = raw.get("variant", "v1")

        profile = raw.get("profile") or {}
        self.w = int(profile.get("w", 1080))
        self.h = int(profile.get("h", 1920))
        self.fps = int(profile.get("fps", 60))

        frame = raw.get("source_frame") or {}
        self.src_w = int(frame.get("w", 2160))
        self.src_h = int(frame.get("h", 3840))

        self.grade = raw.get("grade", "")
        self.stabilize = set(raw.get("stabilize") or [])
        self.total = float(raw["total_seconds"]) if raw.get("total_seconds") else None

        self.crf_segment = int(raw.get("crf_segment", 11))
        self.crf_master = int(raw.get("crf_master", 10))

    def path(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else self.project_dir / p

    @property
    def seg_dir(self) -> Path:
        return self.project_dir / "assets" / "video" / f"seg_{self.variant}"

    @property
    def live_dir(self) -> Path:
        return self.project_dir / "assets" / "audio" / f"live_{self.variant}"

    @property
    def stab_dir(self) -> Path:
        return self.project_dir / "assets" / "video" / f"_stab_{self.variant}"

    @property
    def audio_dir(self) -> Path:
        return self.project_dir / "assets" / "audio"

    @property
    def master(self) -> Path:
        return self.project_dir / "assets" / "video" / f"picture_master_{self.variant}.mp4"

    def artifact(self, key: str) -> Any:
        """Load a declared artifact, or None if it is not declared or not there.

        A declared-but-missing file is a spec problem, not a crash — the doctor
        reports it by name via :meth:`artifact_problem`.
        """
        rel = self.raw.get(key)
        if not rel:
            return None
        p = self.path(rel)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def artifact_problem(self, key: str) -> Optional[str]:
        """Say what is wrong with a declared artifact, or None if it is fine."""
        rel = self.raw.get(key)
        if not rel:
            return None
        p = self.path(rel)
        if not p.exists():
            return f"{key} is declared as {rel!r} but that file does not exist"
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return f"{key} at {rel!r} is not readable JSON: {exc}"
        return None

    def a(self, name: str) -> str:
        """A variant-tagged path inside the audio dir, as a forward-slash string."""
        return str(self.audio_dir / f"{name}_{self.variant}.wav").replace("\\", "/")


# --------------------------------------------------------------------------- #
# stage: picture
# --------------------------------------------------------------------------- #

def stage_picture(spec: ReelSpec, force: bool, log: list[str]) -> dict[str, Any]:
    """Cut, stabilise, grade and scale every segment; pull live audio."""
    cutlist = spec.artifact("cutlist")
    if not cutlist:
        return {"error": spec.artifact_problem("cutlist") or "no cutlist to build from"}
    cuts = cutlist["cuts"] if isinstance(cutlist, dict) else cutlist
    for d in (spec.seg_dir, spec.live_dir, spec.stab_dir):
        d.mkdir(parents=True, exist_ok=True)

    built, skipped, failed = 0, 0, []
    for c in cuts:
        cid = c["id"]
        out = spec.seg_dir / f"seg_{cid}_{c['beat']}.mp4"
        if out.exists() and not force:
            skipped += 1
            continue

        src = spec.source_dir / (c["src"] + c.get("ext", ".MOV"))
        if not src.exists():
            failed.append(f"{cid}: source missing ({src.name})")
            continue

        speed = float(c.get("speed", 1.0))
        crop = float(c.get("crop", 1.0))
        src_len = c["out"] - c["in"]
        nframes = max(2, int(round(src_len / speed * spec.fps)))

        # crop straight out of the native frame — a 1080-wide crop from a 2160
        # source is native pixels, never an upscale
        cw, ch = _even(spec.src_w / crop), _even(spec.src_h / crop)
        crop_f = f"crop={cw}:{ch}:(in_w-{cw})/2:(in_h-{ch})/2,"
        mid_f = f"scale={_even(spec.w * 1.10)}:{_even(spec.h * 1.10)}:flags=lanczos,"
        scale_f = f"scale={spec.w}:{spec.h}:flags=lanczos,"

        stab_f = ""
        if cid in spec.stabilize or c.get("stab"):
            trf = str(spec.stab_dir / f"{cid}.trf").replace("\\", "/")
            _run(["ffmpeg", "-v", "error", "-ss", str(c["in"]), "-t", str(src_len), "-i", str(src),
                  "-vf", f"{crop_f}{mid_f}vidstabdetect=shakiness=7:accuracy=12:stepsize=6:result={trf}",
                  "-f", "null", "-"], f"stab detect {cid}", log)
            if os.path.exists(trf):
                stab_f = "vidstabtransform=input=" + trf + ":zoom=0:smoothing=26:optzoom=1:interpol=bilinear,"

        grade = (spec.grade + ",") if spec.grade else ""
        vf = f"{crop_f}{mid_f}{stab_f}setpts=PTS/{speed},fps={spec.fps},{scale_f}{grade}format=yuv420p10le"

        ok = _run(["ffmpeg", "-v", "error", "-ss", str(c["in"]), "-t", str(src_len), "-i", str(src),
                   "-an", "-vf", vf, "-frames:v", str(nframes),
                   "-c:v", "libx264", "-preset", "slow", "-crf", str(spec.crf_segment),
                   "-pix_fmt", "yuv420p10le", "-y", str(out)], f"segment {cid}", log)
        if ok:
            built += 1
        else:
            failed.append(f"{cid}: encode failed")

        # pull the clip's own audio when this beat is meant to carry live sound
        lv = c.get("live")
        if lv and speed == 1.0:
            ap = spec.live_dir / f"live_{cid}.wav"
            if not ap.exists() or force:
                _run(["ffmpeg", "-v", "error", "-ss", str(c["in"]), "-t", str(src_len), "-i", str(src),
                      "-vn", "-af",
                      "aresample=48000,highpass=f=70,lowpass=f=13500,"
                      f"afade=t=in:st=0:d=0.12,afade=t=out:st={max(0, src_len - 0.35)}:d=0.35,"
                      f"volume={lv}",
                      "-c:a", "pcm_s16le", "-ac", "2", "-y", str(ap)], f"live audio {cid}", log)

    return {"built": built, "skipped": skipped, "failed": failed, "cuts": len(cuts)}


# --------------------------------------------------------------------------- #
# stage: assemble
# --------------------------------------------------------------------------- #

def stage_assemble(spec: ReelSpec, force: bool, log: list[str]) -> dict[str, Any]:
    """Concat cuts into blocks, then chain the blocks with xfade transitions."""
    cutlist = spec.artifact("cutlist")
    if not cutlist:
        return {"error": spec.artifact_problem("cutlist") or "no cutlist to assemble"}
    cuts = cutlist["cuts"] if isinstance(cutlist, dict) else cutlist
    raw_trans = cutlist.get("transitions") if isinstance(cutlist, dict) else None
    transitions = {t["after"]: t for t in (raw_trans or [])}

    if spec.master.exists() and not force:
        return {"master": str(spec.master), "skipped": True,
                "duration": _probe_duration(str(spec.master))}

    # a block ends wherever a transition is declared; cuts inside a block are
    # hard cuts and concat losslessly
    blocks: list[dict[str, Any]] = []
    cur: list[dict[str, Any]] = []
    for c in cuts:
        cur.append(c)
        if c["id"] in transitions:
            blocks.append({"cuts": cur, "trans": transitions[c["id"]]})
            cur = []
    if cur:
        blocks.append({"cuts": cur, "trans": None})

    def seg(c: dict[str, Any]) -> Path:
        return spec.seg_dir / f"seg_{c['id']}_{c['beat']}.mp4"

    missing = [seg(c).name for b in blocks for c in b["cuts"] if not seg(c).exists()]
    if missing:
        return {"error": f"{len(missing)} segments missing — run the picture stage first",
                "missing": missing[:8]}

    seg_dir = str(spec.seg_dir)
    for i, b in enumerate(blocks):
        lst = spec.seg_dir / f"block_{i}.txt"
        lst.write_text("".join(f"file '{seg(c).name}'\n" for c in b["cuts"]), encoding="utf-8")
        bf = spec.seg_dir / f"block_{i}.mp4"
        _run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0",
              "-i", lst.name, "-c", "copy", "-y", bf.name],
             f"block {i} ({len(b['cuts'])} cuts)", log, cwd=seg_dir)
        b["file"] = str(bf).replace("\\", "/")
        probed = _probe_duration(b["file"])
        b["dur"] = probed if probed else sum(
            (c["out"] - c["in"]) / c.get("speed", 1.0) for c in b["cuts"]
        )

    ins: list[str] = []
    for b in blocks:
        ins += ["-i", b["file"]]

    filt: list[str] = []
    prev_label, prev_len = "0:v", blocks[0]["dur"]
    for i in range(1, len(blocks)):
        t = blocks[i - 1]["trans"]
        d, kind = t["duration"], t["type"]
        offset = round(prev_len - d, 3)
        out_label = f"x{i}"
        filt.append(f"[{prev_label}][{i}:v]xfade=transition={kind}:duration={d}:offset={offset}[{out_label}]")
        prev_len = round(prev_len + blocks[i]["dur"] - d, 3)
        prev_label = out_label
    filt.append(f"[{prev_label}]fps={spec.fps},format=yuv420p[v]")

    spec.master.parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-v", "error", *ins, "-filter_complex", ";".join(filt),
          "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "slow",
          "-crf", str(spec.crf_master), "-pix_fmt", "yuv420p", "-y", str(spec.master)],
         "picture master", log)

    if not spec.master.exists():
        return {"error": "picture master was not produced"}
    return {"master": str(spec.master), "blocks": len(blocks),
            "duration": _probe_duration(str(spec.master))}


# --------------------------------------------------------------------------- #
# stage: audio
# --------------------------------------------------------------------------- #

def _build_ambience(spec: ReelSpec, total: float, log: list[str]) -> Optional[str]:
    """Chain speech-free ambience takes into a bed that outlives the cut."""
    amb = spec.raw.get("ambience") or {}
    sources = amb.get("sources") or []
    if not sources:
        return None

    ins: list[str] = []
    filt: list[str] = []
    for i, s in enumerate(sources):
        src = spec.source_dir / s["src"] if not Path(s["src"]).is_absolute() else Path(s["src"])
        ins += ["-ss", str(s.get("ss", 0)), "-t", str(s["t"]), "-i", str(src)]
        filt.append(f"[{i}:a]aresample=48000,highpass=f=70,lowpass=f=13000[a{i}]")

    xf = float(amb.get("crossfade", 4))
    prev = "[a0]"
    for i in range(1, len(sources)):
        label = f"[ab{i}]" if i < len(sources) - 1 else "[abz]"
        filt.append(f"{prev}[a{i}]acrossfade=d={xf}:c1=tri:c2=tri{label}")
        prev = label

    chain = amb.get("volume_expr") or f"volume={amb.get('volume', 0.5)}"
    norm = amb.get("dynaudnorm", "dynaudnorm=f=300:g=9:p=0.62")
    filt.append(f"{prev}{norm},{chain}[out]")

    out = spec.a("amb")
    ok = _run(["ffmpeg", "-v", "error", *ins, "-filter_complex", ";".join(filt),
               "-map", "[out]", "-t", str(total),
               "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", "-y", out],
              f"ambience bed ({len(sources)} takes)", log)
    return out if ok else None


def _build_live(spec: ReelSpec, total: float, log: list[str]) -> Optional[str]:
    """Lay every cut's own audio onto the timeline at its cut position."""
    cutlist = spec.artifact("cutlist")
    cuts = cutlist["cuts"] if isinstance(cutlist, dict) else cutlist
    timeline = spec.artifact("timeline") or {}

    ins: list[str] = []
    filt: list[str] = []
    tags: list[str] = []
    idx = 0
    for c in cuts:
        if not c.get("live"):
            continue
        f = spec.live_dir / f"live_{c['id']}.wav"
        if not f.exists():
            log.append(f"SKIP  live audio missing for cut {c['id']}")
            continue
        at = timeline.get(c["id"])
        if at is None:
            log.append(f"SKIP  cut {c['id']} has no timeline entry")
            continue
        ms = int(float(at[0] if isinstance(at, (list, tuple)) else at) * 1000)
        ins += ["-i", str(f)]
        filt.append(f"[{idx}:a]aresample=48000,adelay={ms}|{ms}[L{idx}]")
        tags.append(f"[L{idx}]")
        idx += 1

    if not tags:
        return None
    filt.append("".join(tags) + f"amix=inputs={len(tags)}:normalize=0:dropout_transition=0,"
                f"apad=whole_dur={total},atrim=0:{total},"
                "acompressor=threshold=-20dB:ratio=2.5:attack=8:release=200,"
                "alimiter=limit=0.96:level=disabled[out]")
    out = spec.a("live_track")
    ok = _run(["ffmpeg", "-v", "error", *ins, "-filter_complex", ";".join(filt),
               "-map", "[out]", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", "-y", out],
              f"live track ({len(tags)} cuts)", log)
    return out if ok else None


def _build_impacts(spec: ReelSpec, log: list[str]) -> list[tuple[float, str]]:
    """A low sine drop on each measured roar onset — the goal hits land harder."""
    windows = spec.artifact("loud_windows") or []
    cfg = spec.raw.get("impacts") or {}
    if cfg.get("enabled") is False or not windows:
        return []

    onsets: list[float] = []
    for w in windows:
        if isinstance(w, (list, tuple)) and len(w) >= 3:
            onsets.append(float(w[2]))
        elif isinstance(w, dict) and "start" in w:
            onsets.append(float(w["start"]))

    expr = cfg.get(
        "expr",
        "aevalsrc=0.9*sin(2*PI*(60*t-25*t*t))*exp(-3.4*t):d=0.85:s=48000:c=stereo",
    )
    made: list[tuple[float, str]] = []
    for i, t in enumerate(onsets):
        out = str(spec.audio_dir / f"impact_{spec.variant}_{i}.wav").replace("\\", "/")
        ok = _run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", expr,
                   "-af", "highpass=f=22,alimiter=limit=0.9:level=disabled",
                   "-c:a", "pcm_s16le", "-y", out], f"impact {i} @{t:.2f}s", log)
        if ok:
            made.append((t, out))
    return made


def _build_vo(spec: ReelSpec, total: float, log: list[str]) -> Optional[str]:
    """Place each narration line at its scripted time and level the result."""
    vo = spec.artifact("vo_script")
    if not vo:
        return None
    lines = vo.get("lines") if isinstance(vo, dict) else vo
    if not lines:
        return None

    vo_dir = spec.path(spec.raw.get("vo_audio_dir") or f"assets/audio/vo_{spec.variant}")
    ins: list[str] = []
    filt: list[str] = []
    tags: list[str] = []
    idx = 0
    for line in lines:
        clip = vo_dir / f"{line['id']}.mp3"
        if not clip.exists():
            log.append(f"SKIP  voiceover clip missing: {clip.name}")
            continue
        ms = int(float(line["at"]) * 1000)
        ins += ["-i", str(clip)]
        filt.append(f"[{idx}:a]aresample=48000,adelay={ms}|{ms}[v{idx}]")
        tags.append(f"[v{idx}]")
        idx += 1

    if not tags:
        return None
    filt.append("".join(tags) + f"amix=inputs={len(tags)}:normalize=0:dropout_transition=0,"
                f"apad=whole_dur={total},atrim=0:{total},"
                "acompressor=threshold=-18dB:ratio=3:attack=5:release=120,"
                "loudnorm=I=-16:TP=-1.5:LRA=7,alimiter=limit=0.95:level=disabled[out]")
    out = spec.a("vo_track")
    ok = _run(["ffmpeg", "-v", "error", *ins, "-filter_complex", ";".join(filt),
               "-map", "[out]", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", "-y", out],
              f"voiceover track ({len(tags)} lines)", log)
    return out if ok else None


def _build_music(spec: ReelSpec, total: float, log: list[str]) -> Optional[str]:
    """Lay out the music segments and ride the fader through the dip windows."""
    music = spec.raw.get("music") or {}
    segments = music.get("segments") or []
    if not segments:
        return None

    track = spec.path(music["track"])
    ins: list[str] = []
    filt: list[str] = []
    tags: list[str] = []
    for i, s in enumerate(segments):
        ins += ["-ss", str(s.get("source_start", 0)), "-i", str(track)]
        parts = [f"[{i}:a]aresample=48000", f"atrim=0:{s['duration']}", "asetpts=PTS-STARTPTS"]
        if s.get("volume") is not None:
            parts.append(f"volume={s['volume']}")
        if s.get("fade_in"):
            parts.append(f"afade=t=in:st=0:d={s['fade_in']}")
        if s.get("fade_out"):
            st = float(s["duration"]) - float(s["fade_out"])
            parts.append(f"afade=t=out:st={st}:d={s['fade_out']}")
        at = int(float(s.get("at", 0)) * 1000)
        if at:
            parts.append(f"adelay={at}|{at}")
        filt.append(",".join(parts) + f"[m{i}]")
        tags.append(f"[m{i}]")

    dip = _dip_expr(music.get("dips") or [], float(music.get("dip_depth", 0.70)),
                    float(music.get("dip_edge", 0.35)))
    filt.append("".join(tags) + f"amix=inputs={len(tags)}:normalize=0:dropout_transition=0,"
                f"apad=whole_dur={total},atrim=0:{total},"
                f"volume={music.get('level', 0.86)},{dip}[out]")

    out = spec.a("music")
    ok = _run(["ffmpeg", "-v", "error", *ins, "-filter_complex", ";".join(filt),
               "-map", "[out]", "-ac", "2", "-c:a", "pcm_s16le", "-y", out],
              f"music bed ({len(segments)} segments)", log)
    return out if ok else None


def _mix(spec: ReelSpec, total: float, tracks: dict[str, Any], with_music: bool,
         out_path: str, log: list[str]) -> bool:
    """Mix bed + live + voice (+ music) through the sidechain chain.

    Three ducks, in order of priority: the crowd ducks the bed, the voice ducks
    the bed, and the voice ducks the crowd — so a line is never buried under the
    stand. Music, when present, gets its own gentler chain: audible under
    narration, still beaten by a goal.
    """
    duck = spec.raw.get("ducking") or {}
    ins: list[str] = []
    filt: list[str] = []
    tags: list[str] = []
    idx = 0

    def add(path: str, at: float, vol: float, tag: str) -> None:
        nonlocal idx
        ins.extend(["-i", path])
        ms = int(at * 1000)
        filt.append(f"[{idx}:a]aresample=48000,volume={vol},adelay={ms}|{ms}[{tag}]")
        tags.append(f"[{tag}]")
        idx += 1

    if tracks.get("ambience"):
        add(tracks["ambience"], 0.0, 1.00 if with_music else 1.20, "amb")
    for name, path, vol in tracks.get("extra_beds", []):
        add(path, 0.0, vol, name)
    for i, (at, path) in enumerate(tracks.get("impacts", [])):
        add(path, at, float(duck.get("impact_level", 0.62)), f"imp{i}")

    if not tags:
        log.append("FAIL  mix has no bed tracks")
        return False
    filt.append("".join(tags) + f"amix=inputs={len(tags)}:normalize=0:dropout_transition=0[bed]")

    live, vo, music = tracks.get("live"), tracks.get("vo"), tracks.get("music")
    li = vi = mi = None
    if live:
        ins += ["-i", live]
        li = idx
        idx += 1
    if vo:
        ins += ["-i", vo]
        vi = idx
        idx += 1
    if with_music and music:
        ins += ["-i", music]
        mi = idx
        idx += 1

    use_music = mi is not None
    stage = "[bed]"

    if li is not None:
        n = 3 if use_music else 2
        labels = "[live_a][live_key][live_key2]" if use_music else "[live_a][live_key]"
        filt.append(f"[{li}:a]aresample=48000,asplit={n}{labels}")
    if vi is not None:
        n = 4 if use_music else 3
        labels = "[vo_a][vo_key][vo_key2][vo_key3]" if use_music else "[vo_a][vo_key][vo_key3]"
        filt.append(f"[{vi}:a]aresample=48000,volume={duck.get('vo_level', 1.05)},asplit={n}{labels}")

    if li is not None:
        filt.append(f"{stage}[live_key]sidechaincompress="
                    f"threshold={duck.get('crowd_over_bed', 0.045)}:ratio=8:"
                    "attack=8:release=320:makeup=1[bed1]")
        stage = "[bed1]"
    if vi is not None:
        filt.append(f"{stage}[vo_key]sidechaincompress="
                    f"threshold={duck.get('vo_over_bed', 0.040)}:ratio=8:"
                    "attack=10:release=280:makeup=1[bed2]")
        stage = "[bed2]"

    parts = stage
    n = 1
    if li is not None:
        if vi is not None:
            filt.append(f"[live_a][vo_key3]sidechaincompress="
                        f"threshold={duck.get('vo_over_crowd', 0.040)}:ratio=6:"
                        "attack=12:release=320:makeup=1[live_d]")
            parts += "[live_d]"
        else:
            parts += "[live_a]"
        n += 1
    if vi is not None:
        parts += "[vo_a]"
        n += 1

    if use_music:
        filt.append(f"[{mi}:a]aresample=48000[mus0]")
        cur = "[mus0]"
        if li is not None:
            filt.append(f"{cur}[live_key2]sidechaincompress="
                        f"threshold={duck.get('crowd_over_music', 0.060)}:ratio=3:"
                        "attack=14:release=420:makeup=1[mus1]")
            cur = "[mus1]"
        if vi is not None:
            filt.append(f"{cur}[vo_key2]sidechaincompress="
                        f"threshold={duck.get('vo_over_music', 0.022)}:ratio=14:"
                        "attack=6:release=300:makeup=1[mus2]")
            cur = "[mus2]"
        parts += cur
        n += 1

    loud = spec.raw.get("loudness") or {}
    filt.append(parts + f"amix=inputs={n}:normalize=0:dropout_transition=0,"
                f"atrim=0:{total},aresample=48000,"
                f"loudnorm=I={loud.get('i', -14)}:TP={loud.get('tp', -1.5)}:LRA={loud.get('lra', 11)},"
                "aresample=192000,alimiter=limit=0.85:level=disabled,aresample=48000[out]")

    return _run(["ffmpeg", "-v", "error", *ins, "-filter_complex", ";".join(filt),
                 "-map", "[out]", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
                 "-y", out_path], f"mix ({'music' if with_music else 'no music'})", log)


def stage_audio(spec: ReelSpec, force: bool, log: list[str]) -> dict[str, Any]:
    """Build every audio layer, then the mixes."""
    total = spec.total or _probe_duration(str(spec.master))
    if not total:
        return {"error": "total_seconds is not set and the picture master is missing"}
    spec.audio_dir.mkdir(parents=True, exist_ok=True)

    tracks: dict[str, Any] = {
        "ambience": _build_ambience(spec, total, log),
        "live": _build_live(spec, total, log),
        "impacts": _build_impacts(spec, log),
        "vo": _build_vo(spec, total, log),
        "music": _build_music(spec, total, log),
        "extra_beds": [],
    }

    # any pre-rendered extra track (a designed SFX pass, a stinger bed)
    for extra in spec.raw.get("extra_beds") or []:
        p = spec.path(extra["path"])
        if p.exists():
            tracks["extra_beds"].append((extra.get("name", "extra"), str(p).replace("\\", "/"),
                                         float(extra.get("volume", 0.85))))
        else:
            log.append(f"SKIP  extra bed missing: {p.name}")

    mixes: dict[str, str] = {}
    for want_music in (True, False):
        if want_music and not tracks["music"]:
            continue
        name = "mix_music" if want_music else "mix_nomusic"
        out = spec.a(name)
        if _mix(spec, total, tracks, want_music, out, log):
            mixes[name] = out

    return {"total_seconds": total, "mixes": mixes,
            "layers": {k: bool(v) for k, v in tracks.items() if k != "extra_beds"},
            "impacts": len(tracks["impacts"])}


# --------------------------------------------------------------------------- #
# stage: deliver
# --------------------------------------------------------------------------- #

def stage_deliver(spec: ReelSpec, force: bool, log: list[str]) -> dict[str, Any]:
    """Mux the graphics render against each mix into the final deliverables."""
    gfx_rel = spec.raw.get("graphics")
    gfx = spec.path(gfx_rel) if gfx_rel else spec.master
    if not gfx.exists():
        return {"error": f"picture source missing: {gfx}"}

    out_dir = spec.path(spec.raw.get("output_dir") or f"renders_{spec.variant}")
    out_dir.mkdir(parents=True, exist_ok=True)
    enc = spec.raw.get("encode") or {}

    produced = []
    for d in spec.raw.get("deliverables") or []:
        mix = spec.a(d["mix"]) if not d["mix"].endswith(".wav") else str(spec.path(d["mix"]))
        if not os.path.exists(mix):
            log.append(f"SKIP  {d['name']}: mix not found ({os.path.basename(mix)})")
            continue
        out = out_dir / d["name"]
        if out.exists() and not force:
            produced.append({"path": str(out), "skipped": True,
                             "size_mb": round(out.stat().st_size / 1048576, 1)})
            continue

        _run(["ffmpeg", "-v", "error", "-i", str(gfx), "-i", mix,
              "-map", "0:v:0", "-map", "1:a:0",
              "-c:v", "libx264", "-profile:v", "high", "-level", "4.2",
              "-preset", enc.get("preset", "slower"), "-crf", str(enc.get("crf", 13)),
              "-maxrate", enc.get("maxrate", "26M"), "-bufsize", enc.get("bufsize", "52M"),
              "-pix_fmt", "yuv420p", "-r", str(spec.fps),
              "-x264-params", f"keyint={spec.fps * 2}:min-keyint={spec.fps}:scenecut=0",
              "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
              "-c:a", "aac", "-b:a", enc.get("audio_bitrate", "320k"), "-ar", "48000", "-ac", "2",
              "-movflags", "+faststart", "-shortest", "-y", str(out)],
             f"deliver {d['name']}", log)

        if out.exists():
            produced.append({"path": str(out), "note": d.get("note", ""),
                             "size_mb": round(out.stat().st_size / 1048576, 1),
                             "duration": _probe_duration(str(out))})

    return {"deliverables": produced, "output_dir": str(out_dir)}


# --------------------------------------------------------------------------- #
# tool
# --------------------------------------------------------------------------- #

class ReelBuilder(BaseTool):
    """Build a highlight reel from real footage — no generated frames."""

    name = "reel_builder"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "ffmpeg"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    # Picture is bit-reproducible. Audio is not, quite: `sidechaincompress` and
    # `apad=whole_dur` into a multi-input `amix` flush their tails differently
    # from run to run when the input streams have unequal lengths. Measured on
    # an 88s reel the divergence is confined to the final ~90ms at -41 dBFS —
    # inaudible, but it means two runs are not byte-identical.
    determinism = Determinism.STOCHASTIC
    resume_support = ResumeSupport.FROM_CHECKPOINT

    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = (
        "Install FFmpeg with libvidstab and libx264: https://ffmpeg.org/download.html\n"
        "Verify with: ffmpeg -filters | grep vidstab"
    )
    agent_skills = ["ffmpeg", "video-edit", "video-toolkit"]
    capabilities = [
        "cut_segments_from_source_footage",
        "stabilise_and_grade_segments",
        "assemble_with_transitions",
        "mix_ambience_live_voice_music",
        "mux_graphics_and_deliver",
    ]
    best_for = [
        "Matchday and highlight reels cut from footage the user shot",
        "Vertical social cuts that need a real crowd bed under narration",
        "Reproducible re-cuts: change the cutlist, rerun, same treatment",
    ]
    not_good_for = [
        "Generating footage that was never filmed",
        "Long-form edits where every cut needs individual attention",
    ]

    input_schema = {
        "type": "object",
        "required": ["spec"],
        "properties": {
            "spec": {"type": ["string", "object"],
                     "description": "Path to a reel spec JSON, or the spec inline"},
            "stages": {"type": "array", "items": {"type": "string", "enum": list(STAGES)},
                       "description": "Stages to run, in order. Defaults to all four."},
            "force": {"type": "boolean", "default": False,
                      "description": "Rebuild outputs that already exist"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "stages": {"type": "object"},
            "log": {"type": "array", "items": {"type": "string"}},
        },
    }
    artifact_schema = {"artifact": "render_report"}

    resource_profile = ResourceProfile(cpu_cores=4, ram_mb=4096, disk_mb=20000)
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["spec", "stages"]
    side_effects = [
        "writes segment, audio and render files under the project directory",
        "runs ffmpeg — long-running and CPU-heavy",
    ]
    user_visible_verification = [
        "Watch the delivered file end to end",
        "Check narration is audible over the crowd at every goal",
        "Confirm no segment upscales past the source resolution",
    ]

    def get_status(self):
        from tools.base_tool import ToolStatus
        import shutil
        ok = shutil.which("ffmpeg") and shutil.which("ffprobe")
        return ToolStatus.AVAILABLE if ok else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # entirely local

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        log: list[str] = []

        raw = inputs.get("spec")
        if isinstance(raw, str):
            spec_path = Path(raw)
            if not spec_path.exists():
                return ToolResult(success=False, error=f"spec not found: {raw}")
            raw = json.loads(spec_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return ToolResult(success=False, error="spec must be a path or an object")

        try:
            spec = ReelSpec(raw)
        except KeyError as exc:
            return ToolResult(success=False, error=f"spec is missing a required field: {exc}")

        wanted = inputs.get("stages") or list(STAGES)
        unknown = [s for s in wanted if s not in STAGES]
        if unknown:
            return ToolResult(success=False, error=f"unknown stages: {unknown}")
        force = bool(inputs.get("force", False))

        runners = {
            "picture": stage_picture,
            "assemble": stage_assemble,
            "audio": stage_audio,
            "deliver": stage_deliver,
        }

        results: dict[str, Any] = {}
        artifacts: list[str] = []
        for name in STAGES:
            if name not in wanted:
                continue
            out = runners[name](spec, force, log)
            results[name] = out
            if out.get("error"):
                return ToolResult(
                    success=False,
                    error=f"stage '{name}': {out['error']}",
                    data={"stages": results, "log": log},
                    duration_seconds=time.time() - start,
                )
            for d in out.get("deliverables", []):
                artifacts.append(d["path"])

        return ToolResult(
            success=True,
            data={"stages": results, "log": log, "variant": spec.variant},
            artifacts=artifacts,
            cost_usd=0.0,
            duration_seconds=time.time() - start,
        )


# --------------------------------------------------------------------------- #
# doctor
# --------------------------------------------------------------------------- #

class _Report:
    """Errors block the build; warnings are worth reading but not fatal."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.checks: dict[str, Any] = {}

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def _probe_cache(path: str, cache: dict[str, Optional[float]]) -> Optional[float]:
    if path not in cache:
        cache[path] = _probe_duration(path)
    return cache[path]


def _check_sources(spec: ReelSpec, cuts: list[dict], rep: _Report,
                   cache: dict[str, Optional[float]]) -> None:
    """Every cut must point at a file that exists and be inside its runtime."""
    missing: set[str] = set()
    overruns: list[str] = []
    for c in cuts:
        src = spec.source_dir / (c["src"] + c.get("ext", ".MOV"))
        if not src.exists():
            missing.add(src.name)
            continue
        if c["out"] <= c["in"]:
            rep.error(f"cut {c['id']}: out ({c['out']}) is not after in ({c['in']})")
            continue
        dur = _probe_cache(str(src), cache)
        if dur is not None and c["out"] > dur + 0.05:
            overruns.append(f"cut {c['id']} wants {c['out']:.2f}s of {src.name}, which is {dur:.2f}s long")
    for m in sorted(missing):
        rep.error(f"source clip not found: {m}")
    for o in overruns:
        rep.error(o)
    rep.checks["sources_ok"] = not missing and not overruns


def _check_timeline(spec: ReelSpec, cuts: list[dict], rep: _Report) -> None:
    """Live cuts need a timeline slot, and the reel needs a declared length."""
    timeline = spec.artifact("timeline") or {}
    if not timeline:
        rep.warn("no timeline artifact — live audio cannot be placed")
        return

    missing = [c["id"] for c in cuts if c.get("live") and c["id"] not in timeline]
    for cid in missing:
        rep.error(f"cut {cid} carries live sound but has no timeline entry")

    if spec.total:
        late = []
        for cid, at in timeline.items():
            start = float(at[0] if isinstance(at, (list, tuple)) else at)
            if start > spec.total:
                late.append(f"{cid} starts at {start:.2f}s, past the {spec.total}s end")
        for line in late:
            rep.warn(line)
    rep.checks["timeline_ok"] = not missing


def _check_voiceover(spec: ReelSpec, rep: _Report) -> None:
    """Every scripted line needs a rendered clip, or it silently vanishes."""
    vo = spec.artifact("vo_script")
    if not vo:
        rep.checks["voiceover"] = "none"
        return
    lines = vo.get("lines") if isinstance(vo, dict) else vo
    vo_dir = spec.path(spec.raw.get("vo_audio_dir") or f"assets/audio/vo_{spec.variant}")
    if not vo_dir.exists():
        rep.error(f"voiceover directory not found: {vo_dir}")
        return

    missing = [line["id"] for line in lines if not (vo_dir / f"{line['id']}.mp3").exists()]
    for mid in missing:
        rep.error(f"voiceover clip missing: {mid}.mp3")
    if spec.total:
        for line in lines:
            if float(line["at"]) > spec.total:
                rep.warn(f"voiceover line {line['id']} is placed at {line['at']}s, past the end")
    rep.checks["voiceover"] = f"{len(lines) - len(missing)}/{len(lines)} clips present"


def _check_audio_beds(spec: ReelSpec, rep: _Report, cache: dict[str, Optional[float]]) -> None:
    """Ambience takes, music segments and any extra bed must all resolve."""
    amb = spec.raw.get("ambience") or {}
    for s in amb.get("sources") or []:
        p = spec.source_dir / s["src"]
        if not p.exists():
            rep.error(f"ambience take not found: {s['src']}")
            continue
        dur = _probe_cache(str(p), cache)
        want = float(s.get("ss", 0)) + float(s["t"])
        if dur is not None and want > dur + 0.05:
            rep.error(f"ambience take {s['src']}: wants {want:.2f}s but the clip is {dur:.2f}s")

    music = spec.raw.get("music") or {}
    if music.get("track"):
        track = spec.path(music["track"])
        if not track.exists():
            rep.error(f"music track not found: {music['track']}")
        else:
            dur = _probe_cache(str(track), cache)
            for i, seg in enumerate(music.get("segments") or []):
                want = float(seg.get("source_start", 0)) + float(seg["duration"])
                if dur is not None and want > dur + 0.05:
                    rep.error(f"music segment {i}: wants {want:.2f}s of a {dur:.2f}s track")
                if spec.total and float(seg.get("at", 0)) >= spec.total:
                    rep.warn(f"music segment {i} starts at {seg.get('at')}s, past the end")

    for extra in spec.raw.get("extra_beds") or []:
        if not spec.path(extra["path"]).exists():
            rep.warn(f"extra bed not found, it will be skipped: {extra['path']}")


def _check_delivery(spec: ReelSpec, rep: _Report, cache: dict[str, Optional[float]]) -> None:
    """The graphics render has to exist and match the reel's length."""
    gfx_rel = spec.raw.get("graphics")
    if gfx_rel:
        gfx = spec.path(gfx_rel)
        if not gfx.exists():
            rep.error(f"graphics render not found: {gfx_rel}")
        else:
            dur = _probe_cache(str(gfx), cache)
            rep.checks["graphics_seconds"] = dur
            if dur and spec.total and abs(dur - spec.total) > 0.5:
                rep.warn(f"graphics is {dur:.2f}s but the reel is {spec.total}s — "
                         "-shortest will trim to whichever ends first")

    names = {d["name"] for d in spec.raw.get("deliverables") or []}
    if len(names) != len(spec.raw.get("deliverables") or []):
        rep.error("two deliverables share a filename — one would overwrite the other")
    if not names:
        rep.warn("no deliverables declared — the deliver stage will produce nothing")

    has_music = bool((spec.raw.get("music") or {}).get("segments"))
    for d in spec.raw.get("deliverables") or []:
        if d["mix"] == "mix_music" and not has_music:
            rep.error(f"deliverable {d['name']} asks for the music mix, but no music is configured")


def _check_environment(spec: ReelSpec, rep: _Report) -> None:
    """ffmpeg has to be there, and it has to have vidstab if we plan to use it."""
    import shutil
    for exe in ("ffmpeg", "ffprobe"):
        if not shutil.which(exe):
            rep.error(f"{exe} is not on PATH")
    if spec.stabilize and shutil.which("ffmpeg"):
        filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                                 capture_output=True, text=True).stdout
        if "vidstabdetect" not in filters:
            rep.error(f"{len(spec.stabilize)} cuts ask for stabilisation but this "
                      "ffmpeg has no vidstab — rebuild it with --enable-libvidstab")


class ReelDoctor(BaseTool):
    """Check a reel spec before committing to a long render."""

    name = "reel_doctor"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "analysis"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffprobe"]
    install_instructions = "Install FFmpeg: https://ffmpeg.org/download.html"
    agent_skills = ["ffmpeg", "video-edit"]
    capabilities = ["validate_reel_spec", "preflight_before_render"]
    best_for = [
        "Catching a missing clip or an out-of-range cut before an hour of encoding",
        "Confirming a spec still resolves after footage has been moved",
    ]
    not_good_for = ["Judging whether the edit is any good"]

    input_schema = {
        "type": "object",
        "required": ["spec"],
        "properties": {
            "spec": {"type": ["string", "object"]},
            "probe": {"type": "boolean", "default": True,
                      "description": "Probe every source with ffprobe. Slower, but the "
                                     "only way to catch a cut that runs past the end of its clip."},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "ok": {"type": "boolean"},
            "errors": {"type": "array", "items": {"type": "string"}},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "checks": {"type": "object"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, disk_mb=1)
    retry_policy = RetryPolicy(max_retries=0)
    side_effects = ["reads media headers; writes nothing"]
    user_visible_verification = ["Read the errors — each names the exact cut or file at fault"]

    def get_status(self):
        from tools.base_tool import ToolStatus
        import shutil
        return ToolStatus.AVAILABLE if shutil.which("ffprobe") else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        raw = inputs.get("spec")
        if isinstance(raw, str):
            p = Path(raw)
            if not p.exists():
                return ToolResult(success=False, error=f"spec not found: {raw}")
            raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return ToolResult(success=False, error="spec must be a path or an object")

        try:
            spec = ReelSpec(raw)
        except KeyError as exc:
            return ToolResult(success=False, error=f"spec is missing a required field: {exc}")

        rep = _Report()
        cache: dict[str, Optional[float]] = {}
        probe = inputs.get("probe", True)

        _check_environment(spec, rep)

        for key in ("cutlist", "timeline", "vo_script", "loud_windows"):
            problem = spec.artifact_problem(key)
            if problem:
                rep.error(problem)

        cutlist = spec.artifact("cutlist")
        if not cutlist:
            if not spec.artifact_problem("cutlist"):
                rep.error("no cutlist — there is nothing to cut")
            return ToolResult(success=True, data={"ok": False, "errors": rep.errors,
                                                  "warnings": rep.warnings, "checks": rep.checks},
                              duration_seconds=time.time() - start)

        cuts = cutlist["cuts"] if isinstance(cutlist, dict) else cutlist
        rep.checks["cuts"] = len(cuts)
        rep.checks["reel_seconds"] = spec.total

        ids = [c["id"] for c in cuts]
        dupes = {i for i in ids if ids.count(i) > 1}
        for d in sorted(dupes):
            rep.error(f"cut id {d} appears more than once — segment files would collide")

        unknown_stab = spec.stabilize - set(ids)
        for s in sorted(unknown_stab):
            rep.warn(f"stabilize lists {s}, which is not a cut in this cutlist")

        if isinstance(cutlist, dict):
            for t in cutlist.get("transitions") or []:
                if t["after"] not in ids:
                    rep.error(f"transition declared after cut {t['after']}, which does not exist")

        planned = sum((c["out"] - c["in"]) / c.get("speed", 1.0) for c in cuts)
        overlap = sum(t.get("duration", 0) for t in
                      (cutlist.get("transitions") or [] if isinstance(cutlist, dict) else []))
        expected = planned - overlap
        rep.checks["expected_seconds"] = round(expected, 3)
        if spec.total and abs(expected - spec.total) > 0.25:
            rep.warn(f"cuts add up to {expected:.2f}s after transitions, but total_seconds "
                     f"says {spec.total} — audio and picture will not line up")

        if probe:
            _check_sources(spec, cuts, rep, cache)
        _check_timeline(spec, cuts, rep)
        _check_voiceover(spec, rep)
        if probe:
            _check_audio_beds(spec, rep, cache)
            _check_delivery(spec, rep, cache)

        return ToolResult(
            success=True,
            data={"ok": not rep.errors, "errors": rep.errors,
                  "warnings": rep.warnings, "checks": rep.checks},
            duration_seconds=time.time() - start,
        )
