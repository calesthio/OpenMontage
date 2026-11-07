#!/usr/bin/env python3
"""scripts/run_episode.py — one-command episode pipeline (Milestone Z3).

Usage:  python3 scripts/run_episode.py <topic_id>

Chains: claim_ledger_check -> script_validation -> footage_manifest_rights ->
        narration -> subtitles -> edl -> render -> finish_audio -> qc ->
        package_draft

Per-stage checkpoint with wall-time + disk logging, resume of OK stages,
idempotency via output hashing, fail-closed (any unverified stage = BLOCKED,
pipeline stops, non-zero exit). Stage implementations are pluggable through
STAGE_REGISTRY so tests can drive the orchestration with fake stages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Venv used for the Kokoro / stable-ts toolchain (set up in Milestone Z1).
VENV_PY = Path(os.environ.get("OPENMONTAGE_VENV", "/tmp/kilo/z1_venv/bin/python"))

MIN_FREE_BYTES = 800 * 1024 * 1024  # global stop threshold (zero-cost mode)
MAX_CHAPTER_DURATION = 360  # 6 minutes per chapter (Z4)

STAGES = [
    "claim_ledger_check",
    "script_validation",
    "footage_manifest_rights",
    "narration",
    "subtitles",
    "edl",
    "render",
    "finish_audio",
    "qc",
    "package_draft",
]


def iso_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def disk_free_bytes(path):
    return shutil.disk_usage(str(path)).free


def _hash_obj(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _load_state(state_path):
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))
    return {"topic_id": None, "stages": {}}


def _save_state(state_path, state):
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Topic layout helpers
# ---------------------------------------------------------------------------
def slice_dir(topic_id):
    return ROOT / "docs/openmontage/slice" / topic_id


def topic_script(topic_id):
    candidates = [
        ROOT / f"docs/openmontage/slice/{topic_id.upper()}_FULL_SCRIPT_v0.md",
        slice_dir(topic_id) / "script.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def topic_ledger(topic_id):
    candidates = [
        ROOT / f"docs/openmontage/evidence/{topic_id.upper()}_CLAIM_LEDGER.md",
        ROOT / f"docs/openmontage/slice/{topic_id.upper()}_CLAIM_LEDGER.md",
        slice_dir(topic_id) / "claim_ledger.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def shared_assets():
    return ROOT / "docs/openmontage/slice/artifacts"


def _chap_idx(state):
    return state.get("chapter_index")


def _narration_paths(topic_id, state):
    """Per-chapter narration wavs so chapters don't clobber each other."""
    base = slice_dir(topic_id)
    chap = _chap_idx(state)
    tag = f"_chapter{chap}" if chap is not None else ""
    return base / f"narration_raw{tag}.wav", base / f"narration_finished{tag}.wav"


def _render_out(topic_id, state):
    base = slice_dir(topic_id) / "renders"
    chap = _chap_idx(state)
    tag = f"_chapter{chap}" if chap is not None else ""
    return base / f"final_{topic_id}_draft{tag}.mp4"


def _render_paths(topic_id, state):
    """Per-episode render locations, overridable via state for testing.

    EDL path, render manifest path (asset_id -> file), narration wav and
    output mp4 all default to the slice-dir conventions but can be
    overridden through state keys so the render stage is testable with
    temp files and is not tied to any single episode.
    """
    chap = _chap_idx(state)
    tag = f"_chapter{chap}" if chap is not None else ""
    edl = state.get("edl_path") or slice_dir(topic_id) / f"edit_decisions{tag}.json"
    manifest = state.get("render_manifest_path") or slice_dir(topic_id) / "render_manifest.json"
    wav = state.get("narration_wav") or _narration_paths(topic_id, state)[1]
    out = state.get("render_output_path") or _render_out(topic_id, state)
    return Path(edl), Path(manifest), Path(wav), Path(out)


# ---------------------------------------------------------------------------
# Stage implementations
# ---------------------------------------------------------------------------
def cmd_claim_ledger_check(topic_id, state):
    ledger = topic_ledger(topic_id)
    if not ledger:
        return {"status": "BLOCKED", "error": f"no claim ledger for topic {topic_id}"}
    text = ledger.read_text(encoding="utf-8")
    import re
    ids = re.findall(r"\b[A-Za-z][A-Za-z0-9]*-[0-9]+\b", text)
    claim_ids = sorted(set(ids))
    if not claim_ids:
        return {"status": "BLOCKED", "error": "claim ledger has no claim_ids"}
    return {"status": "OK", "outputs": {"ledger": str(ledger), "claim_ids": claim_ids}}


def cmd_script_validation(topic_id, state):
    script = topic_script(topic_id)
    if not script:
        return {"status": "BLOCKED", "error": f"no script for topic {topic_id}"}
    sentences = [row["sentence"] for row in _parse_script_rows(script)]
    if not sentences:
        return {"status": "BLOCKED",
                "error": f"script {script} has no parseable beat/sentence rows"}
    return {"status": "OK", "outputs": {"script": str(script), "sentences": len(sentences)}}


def cmd_footage_manifest_rights(topic_id, state):
    rights = shared_assets() / "rights_records.json"
    if not rights.exists():
        return {"status": "BLOCKED", "error": "rights_records.json missing"}
    records = json.loads(rights.read_text(encoding="utf-8"))
    allowed = {"explicit_license", "source_policy_us_gov"}
    bad = [r["asset_id"] for r in records if r.get("rights_basis") not in allowed]
    if bad:
        return {"status": "BLOCKED", "error": f"rights_basis not permitted: {bad}"}
    return {"status": "OK", "outputs": {"rights_records": str(rights), "assets": len(records)}}


def cmd_narration(topic_id, state):
    slice_dir(topic_id).mkdir(parents=True, exist_ok=True)
    raw, wav = _narration_paths(topic_id, state)
    if wav.exists():
        return {"status": "OK", "outputs": {"narration_wav": str(wav)}}
    # Chapter mode: synthesize only this chapter's sentences (chapter_script),
    # otherwise the full topic script.
    script = state.get("chapter_script") or topic_script(topic_id)
    if not script:
        return {"status": "BLOCKED", "error": f"no script for topic {topic_id}"}
    if not raw.exists():
        helper = ROOT / "scripts" / "z3_kokoro_narrate.py"
        if not helper.exists():
            return {"status": "BLOCKED", "error": "kokoro narration helper missing"}
        res = subprocess.run(
            [str(VENV_PY), str(helper), str(script), str(raw)],
            capture_output=True, text=True, timeout=1800,
        )
        if res.returncode != 0:
            return {"status": "BLOCKED", "error": f"kokoro synthesis failed: {res.stderr[-500:]}"}
    from tools.audio.finish_audio import FinishAudioTool  # noqa: WPS433
    result = FinishAudioTool().execute(
        {"input_path": str(raw), "output_path": str(wav)}
    )
    if not result.success:
        return {"status": "BLOCKED", "error": f"finish_audio failed: {result.error}"}
    # Record the ACTUAL synthesized duration so QC duration_vs_script compares
    # video against the narration that was actually produced (not a stale value).
    dur = result.data.get("duration_s")
    if dur is None:
        import subprocess as _sp, json as _json
        probe = _sp.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                         "-show_format", str(wav)], capture_output=True, text=True)
        try:
            dur = round(float(_json.loads(probe.stdout)["format"]["duration"]), 6)
        except Exception:
            dur = None
    manifest = {
        "expected_duration": dur,
        "tolerance": 1.0,
        "sample_rate": 44100,
        "voice": "af_heart",
        "engine": "kokoro_onnx_82m_cpu",
        "sentences": len(sentences),
    }
    shared_assets().mkdir(parents=True, exist_ok=True)
    chap = _chap_idx(state)
    mtag = f"_chapter{chap}" if chap is not None else ""
    (shared_assets() / f"narration_manifest{mtag}.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return {"status": "OK", "outputs": {"narration_wav": str(wav), **result.data,
                                        "narration_duration_s": dur}}


def cmd_subtitles(topic_id, state):
    _raw, wav = _narration_paths(topic_id, state)
    if not wav.exists():
        return {"status": "BLOCKED", "error": "no finished narration for subtitles"}
    slice_dir(topic_id).mkdir(parents=True, exist_ok=True)
    chap = _chap_idx(state)
    tag = f"_chapter{chap}" if chap is not None else ""
    words_out = slice_dir(topic_id) / f"word-timestamps{tag}.json"
    srt_out = slice_dir(topic_id) / f"subtitles{tag}.srt"
    if words_out.exists() and srt_out.exists():
        return {"status": "OK", "outputs": {"words": str(words_out), "subtitles": str(srt_out)}}
    helper = ROOT / "scripts" / "z3_subtitles.py"
    if not helper.exists():
        return {"status": "BLOCKED", "error": "subtitle helper missing"}
    script_path = state.get("chapter_script") or topic_script(topic_id)
    if not script_path:
        return {"status": "BLOCKED", "error": f"no script for topic {topic_id}"}
    sentences = []
    for line in Path(script_path).read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("| B"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 3 and cells[0][0] == "B" and cells[0][1:].isdigit():
            sentences.append(cells[1])
    text = " ".join(sentences)
    res = subprocess.run(
        [str(VENV_PY), str(helper), str(wav), text, str(words_out), str(srt_out)],
        capture_output=True, text=True, timeout=1800,
    )
    if res.returncode != 0:
        return {"status": "BLOCKED", "error": f"subtitles failed: {res.stderr[-500:]}"}
    return {"status": "OK", "outputs": {"words": str(words_out), "subtitles": str(srt_out)}}


def _parse_script_rows(script_path):
    """Parse a script markdown table into rows in script order.

    Accepts beat labels of the form ``B<digits>`` or ``B<digits>-<digits>``
    (e.g. ``B1`` and ``B1-2``). Returns ``[{beat, sentence, claim_ids}]``;
    the beat label is normalised to its base (``B1-2`` -> ``B1``).
    """
    import re

    rows = []
    for line in Path(script_path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells:
            continue
        match = re.match(r"^B(\d+)(?:-\d+)?$", cells[0])
        if not match:
            continue
        sentence = cells[1] if len(cells) > 1 else ""
        if not sentence:
            continue
        claim_ids = cells[2] if len(cells) > 2 else ""
        rows.append({
            "beat": f"B{match.group(1)}",
            "sentence": sentence,
            "claim_ids": claim_ids,
        })
    return rows


def _group_beats(rows):
    """Group script rows into ordered beats, preserving first-seen order."""
    beats = []
    index = {}
    for row in rows:
        beat = row["beat"]
        if beat not in index:
            index[beat] = {"beat": beat, "rows": []}
            beats.append(index[beat])
        index[beat]["rows"].append(row)
    return beats


def _beat_claim_ids(beat):
    """Union of the claim_ids cited by a beat's sentences, in first-seen order."""
    import re

    ids = []
    for row in beat["rows"]:
        for part in re.split(r"[,;]", row["claim_ids"]):
            part = part.strip()
            if part and part not in ids:
                ids.append(part)
    return ids


def _episode_narration_duration(topic_id, state):
    """Measured narration duration, or None. No invented fallback values.

    Sources, in order: explicit ``narration_duration_s``, an explicit
    ``narration_manifest_path``, this episode's narration wav. The shared
    artifacts manifest is deliberately NOT used implicitly: it belongs to
    whichever episode wrote it last.
    """
    explicit = state.get("narration_duration_s")
    if explicit is not None:
        return float(explicit)
    manifest = state.get("narration_manifest_path")
    if manifest and Path(manifest).is_file():
        try:
            data = json.loads(Path(manifest).read_text(encoding="utf-8"))
            dur = data.get("expected_duration")
            if dur:
                return float(dur)
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
    wav = Path(state.get("narration_wav") or _narration_paths(topic_id, state)[1])
    if wav.is_file():
        return _ffprobe_duration(wav)
    return None


def cmd_edl(topic_id, state):
    """Build an episode-generic EDL from the script table + narration duration.

    No topic name, claim ID, asset ID or duration is hardcoded (SCR-07).
    Cuts are original graphics cards (title, one per beat, credits); every
    card is declared ``static_by_design``. Footage insertion stays a later
    asset-inventory concern, not a pipeline constant.
    """
    chap = _chap_idx(state)
    tag = f"_chapter{chap}" if chap is not None else ""
    out = Path(state.get("edl_path") or slice_dir(topic_id) / f"edit_decisions{tag}.json")
    if out.exists():
        return {"status": "OK", "outputs": {"edit_decisions": str(out), "resumed": True}}

    script = state.get("chapter_script") or state.get("script_path") or topic_script(topic_id)
    if not script:
        return {"status": "BLOCKED", "error": f"no script for topic {topic_id}"}
    rows = _parse_script_rows(script)
    if not rows:
        return {"status": "BLOCKED",
                "error": f"script {script} has no parseable beat/sentence rows"}
    total = _episode_narration_duration(topic_id, state)
    if not total or total <= 0:
        return {"status": "BLOCKED",
                "error": "no narration duration (run narration first or pass narration_duration_s)"}

    beats = _group_beats(rows)
    total = round(float(total), 3)
    title_dur = round(min(8.0, total * 0.05), 3)
    credits_plan = round(min(6.0, total * 0.06), 3)
    body = round(total - title_dur - credits_plan, 3)
    if body <= 0:
        return {"status": "BLOCKED",
                "error": f"narration too short for title+credits cards ({total}s)"}

    weights = [max(1, sum(len(r["sentence"]) for r in b["rows"])) for b in beats]
    total_weight = sum(weights)
    raw = [body * w / total_weight for w in weights]
    beat_durs = [round(x, 3) for x in raw]
    beat_durs[-1] = round(body - sum(beat_durs[:-1]), 3)

    cuts = []
    static_segments = []

    def add_card(asset_id, start, duration, clip, rationale, claim_ids=None, beat=None):
        end = round(start + duration, 3)
        cut = {
            "cut_id": len(cuts) + 1,
            "start": round(start, 3),
            "end": end,
            "asset_id": asset_id,
            "role": "graphics_card",
            "clip": clip,
            "layout": "static_card",
            "static_by_design": True,
            "rights_basis": "explicit_license",
            "rationale": rationale,
        }
        if beat:
            cut["beat"] = beat
        if claim_ids:
            cut["claim_ids"] = ", ".join(claim_ids)
        cuts.append(cut)
        static_segments.append({
            "start": cut["start"], "end": end,
            "reason": f"{clip} card", "static_by_design": True,
        })
        return end

    cursor = add_card(
        "card_title", 0.0, title_dur, "Title",
        "Opening title card (original graphic, no factual claim); static by design.",
    )
    for i, beat in enumerate(beats, 1):
        claim_ids = _beat_claim_ids(beat)
        n = len(beat["rows"])
        claims_note = ", ".join(claim_ids) if claim_ids else "none"
        cursor = add_card(
            f"card_b{i}", cursor, beat_durs[i - 1], beat["beat"],
            f"Beat {beat['beat']} card ({n} sentence(s), claim_ids: {claims_note}); "
            f"static by design.",
            claim_ids=claim_ids, beat=beat["beat"],
        )
    credits_dur = round(total - cursor, 3)
    if credits_dur <= 0:
        # Absorb rounding into the last beat card instead of a zero-length card.
        diff = credits_dur
        cuts[-1]["end"] = round(cuts[-1]["end"] + diff, 3)
        static_segments[-1]["end"] = cuts[-1]["end"]
    else:
        add_card("card_credits", cursor, credits_dur, "Credits",
                 "Closing credits card; static by design.")
    cuts[-1]["end"] = total
    static_segments[-1]["end"] = total

    edl = {
        "version": 1,
        "topic_id": topic_id,
        "total_duration_s": total,
        "resolution": state.get("resolution", "1920x1080"),
        "fps": state.get("fps", 30),
        "codec": "h264",
        "audio_codec": "aac",
        "source": "script+narration (episode-generic)",
        "cuts": cuts,
        "static_segments": static_segments,
    }
    if chap is not None:
        edl["chapter_index"] = chap
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(edl, indent=2), encoding="utf-8")
    return {"status": "OK", "outputs": {
        "edit_decisions": str(out),
        "cuts": len(cuts),
        "beats": len(beats),
        "total_duration_s": total,
    }}


def _ffmpeg(args, timeout=3600):
    res = subprocess.run(["ffmpeg", "-hide_banner", "-y"] + args,
                         capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(res.stderr[-800:])


def _ffprobe_duration(path):
    """Return duration in seconds, or None if unreadable."""
    res = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        return None
    try:
        return float(json.loads(res.stdout)["format"]["duration"])
    except Exception:
        return None


def _loop_to_duration(src, target_dur, out):
    """Loop src enough times and trim to exactly target_dur seconds."""
    d = _ffprobe_duration(src) or target_dur
    n = max(1, int(__import__("math").ceil(target_dur / d)))
    lst = Path(src).parent / "loop_concat.txt"
    lst.write_text("\n".join(f"file '{src}'" for _ in range(n)), encoding="utf-8")
    _ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-t", str(target_dur),
             "-c", "copy", str(out)])


def _render_graphics(path, dur, width, height, fps, out):
    """Loop a graphics PNG for dur seconds, scaled to the render resolution."""
    _ffmpeg(["-loop", "1", "-i", str(path), "-t", str(dur),
             "-vf", f"scale={width}:{height}",
             "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
             "-r", str(fps), "-an", str(out)])


def _render_archive(footage, src_start, dur, width, height, fps, out):
    """Trim dur seconds from footage starting at src_start, framed to resolution.

    Footage shorter than needed is loop-filled so the segment is exactly dur.
    """
    vf = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
          f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p")
    tmp = Path(out).parent / (Path(out).stem + "_raw.mp4")
    _ffmpeg(["-ss", str(src_start), "-i", str(footage), "-t", str(dur),
             "-vf", vf, "-c:v", "libx264", "-crf", "18", "-r", str(fps), "-an", str(tmp)])
    actual = _ffprobe_duration(tmp) or 0.0
    if actual < dur - 0.05:
        _loop_to_duration(tmp, dur, out)
        tmp.unlink(missing_ok=True)
    else:
        tmp.replace(out)


def cmd_render(topic_id, state):
    """Render per EDL cuts using per-episode asset paths from the render manifest.

    The render manifest (render_manifest.json) maps each asset_id to a
    {kind, path} record. graphics_card cuts loop a PNG; archive_insert cuts
    trim HD footage (framed/pillarboxed to 1080p when <1080p). All segments
    are rendered to the same resolution/fps and concatenated, then muxed
    with the narration wav. No episode-specific paths are hardcoded.
    """
    edl_path, manifest_path, wav, out = _render_paths(topic_id, state)
    out_dir = out.parent
    if not wav.exists():
        return {"status": "BLOCKED", "error": "no narration wav for render"}
    if not manifest_path.exists():
        return {"status": "BLOCKED", "error": "render manifest missing"}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "BLOCKED", "error": f"render manifest unreadable: {exc}"}
    assets = manifest.get("assets", {})
    if not edl_path.exists():
        return {"status": "BLOCKED", "error": "no EDL to render"}
    try:
        edl = json.loads(edl_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"status": "BLOCKED", "error": f"EDL unreadable: {exc}"}
    cuts = edl.get("cuts", [])
    if not cuts:
        return {"status": "BLOCKED", "error": "EDL has no cuts"}
    width, height = [int(x) for x in str(manifest.get("resolution", "1920x1080")).split("x")]
    fps = int(manifest.get("fps", 30))
    out_dir.mkdir(parents=True, exist_ok=True)
    build = out_dir / "build"
    shutil.rmtree(build, ignore_errors=True)
    build.mkdir()
    segs = []
    for cut in cuts:
        dur = round(float(cut["end"]) - float(cut["start"]), 6)
        asset_id = cut["asset_id"]
        role = cut.get("role")
        asset = assets.get(asset_id)
        if not asset:
            return {"status": "BLOCKED", "error": f"asset {asset_id} not in render manifest"}
        path = asset.get("path")
        kind = asset.get("kind")
        if not path:
            return {"status": "BLOCKED", "error": f"asset {asset_id} has no path"}
        seg = build / f"seg_{len(segs):02d}.mp4"
        if role == "graphics_card" or kind == "graphics":
            if not Path(path).exists():
                return {"status": "BLOCKED", "error": f"graphics asset missing: {path}"}
            _render_graphics(path, dur, width, height, fps, seg)
        elif role == "archive_insert" or kind == "footage":
            if not Path(path).exists():
                return {"status": "BLOCKED", "error": f"footage asset missing: {path}"}
            src_start = 0.0
            src_seg = cut.get("source_segment")
            if src_seg:
                try:
                    src_start = float(str(src_seg).split("-")[0])
                except ValueError:
                    src_start = 0.0
            _render_archive(path, src_start, dur, width, height, fps, seg)
        else:
            return {"status": "BLOCKED", "error": f"unknown role {role} for {asset_id}"}
        actual = _ffprobe_duration(seg) or 0.0
        if actual < dur - 0.05:
            return {"status": "BLOCKED", "error": f"segment {asset_id} too short ({actual}s < {dur}s)"}
        segs.append(str(seg))
    lst = build / "concat.txt"
    lst.write_text("\n".join(f"file '{Path(s).name}'" for s in segs), encoding="utf-8")
    silent = out_dir / "silent.mp4"
    _ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)])
    _ffmpeg(["-i", str(silent), "-i", str(wav), "-c:v", "copy", "-c:a", "aac",
             "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)])
    return {"status": "OK", "outputs": {"video": str(out)}}


def cmd_finish_audio(topic_id, state):
    wav = slice_dir(topic_id) / "narration_finished.wav"
    if not wav.exists():
        return {"status": "BLOCKED", "error": "no narration to finish"}
    # Idempotent: finish_audio output is 44100 Hz; raw kokoro output is 24000 Hz.
    # If already 44100 Hz, narration was finished by the narration stage -> skip.
    import subprocess as _sp, json as _json
    probe = _sp.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                     "-show_streams", str(wav)], capture_output=True, text=True)
    try:
        streams = _json.loads(probe.stdout).get("streams", [])
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        if audio_streams and int(audio_streams[0].get("sample_rate", 0)) == 44100:
            return {"status": "OK", "outputs": {"finished_wav": str(wav),
                                                "already_finished": True}}
    except Exception:
        pass  # fall through to re-finish if probe is inconclusive
    from tools.audio.finish_audio import FinishAudioTool  # noqa: WPS433
    finished = wav.with_name("narration_finished.wav")
    result = FinishAudioTool().execute({"input_path": str(wav), "output_path": str(finished)})
    if not result.success:
        return {"status": "BLOCKED", "error": f"finish_audio failed: {result.error}"}
    return {"status": "OK", "outputs": {"finished_wav": str(finished)}}


def cmd_qc(topic_id, state):
    video = slice_dir(topic_id) / "renders" / f"final_{topic_id}_draft.mp4"
    assets = shared_assets()
    ledger = topic_ledger(topic_id)
    if not video.exists():
        return {"status": "BLOCKED", "error": "no rendered video for QC"}
    if not ledger:
        return {"status": "BLOCKED", "error": f"no claim ledger for topic {topic_id}"}
    chap = _chap_idx(state)
    tag = f"_chapter{chap}" if chap is not None else ""
    inputs = {
        "input_path": str(video),
        "output_path": str(assets / f"qa_report{tag}.json"),
        "narration_manifest": str(shared_assets() / f"narration_manifest{tag}.json"),
        "subtitle_path": str(slice_dir(topic_id) / f"subtitles{tag}.srt"),
        "credits_path": str(assets / "credits.txt"),
        "claim_ids_path": str(assets / "claim_ids.json"),
        "claim_ledger_path": str(ledger),
        "rights_records_path": str(assets / "rights_records.json"),
        "edit_decisions_path": str(slice_dir(topic_id) / f"edit_decisions{tag}.json"),
        "config_path": str(ROOT / "config" / "qc_thresholds.json"),
    }
    for k in ("narration_manifest", "subtitle_path", "credits_path", "claim_ids_path",
              "rights_records_path", "edit_decisions_path"):
        if not Path(inputs[k]).exists():
            return {"status": "BLOCKED", "error": f"missing QC input: {k}"}
    from tools.qa.qc import QCTool  # noqa: WPS433
    res = QCTool().execute(inputs)
    if not res.success:
        return {"status": "BLOCKED", "error": f"qc tool failed: {res.error}"}
    return {"status": "OK", "outputs": {"qa_report": str(inputs["output_path"]),
                                        "verdict": res.data.get("verdict")}}


def cmd_package_draft(topic_id, state):
    pkg = slice_dir(topic_id) / "package"
    pkg.mkdir(parents=True, exist_ok=True)
    assets = shared_assets()
    for name in ("narration_manifest.json", "subtitles.srt", "credits.txt", "edit_decisions.json",
                 "rights_records.json", "claim_ids.json", "word-timestamps.json"):
        src = assets / name
        if src.exists():
            shutil.copy2(src, pkg / name)
    video = slice_dir(topic_id) / "renders" / f"final_{topic_id}_draft.mp4"
    manifest = {
        "topic_id": topic_id, "status": "DRAFT_NOT_PUBLISHABLE",
        "package": str(pkg),
        "video": str(video) if video.exists() else None,
    }
    (pkg / "package_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"status": "OK", "outputs": {"package": str(pkg), "manifest": str(pkg / "package_manifest.json")}}


STAGE_REGISTRY = {
    "claim_ledger_check": cmd_claim_ledger_check,
    "script_validation": cmd_script_validation,
    "footage_manifest_rights": cmd_footage_manifest_rights,
    "narration": cmd_narration,
    "subtitles": cmd_subtitles,
    "edl": cmd_edl,
    "render": cmd_render,
    "finish_audio": cmd_finish_audio,
    "qc": cmd_qc,
    "package_draft": cmd_package_draft,
}


def run_pipeline(topic_id, state_path=None, state_root=None, stages=None, initial_state=None):
    if stages is None:
        stages = STAGE_REGISTRY
    if state_path is None:
        state_root = Path(state_root) if state_root else ROOT / "docs/openmontage/slice"
        state_path = Path(state_root) / topic_id / "episode_state.json"
    state_path = Path(state_path)

    if initial_state is not None:
        state = json.loads(json.dumps(initial_state))
        state["topic_id"] = topic_id
    else:
        state = _load_state(state_path)
    state["topic_id"] = topic_id
    state["updated_at"] = iso_now()
    state.setdefault("stages", {})

    # ---- fail-closed: disk budget before anything runs ----
    if disk_free_bytes(ROOT) < MIN_FREE_BYTES:
        free = disk_free_bytes(ROOT)
        cp = {"status": "BLOCKED", "started_at": iso_now(), "finished_at": iso_now(),
              "wall_time_s": 0.0, "disk_before_bytes": free,
              "disk_after_bytes": free, "outputs": {},
              "output_hash": _hash_obj({}),
              "error": f"free disk {free} bytes below {MIN_FREE_BYTES} bytes"}
        state["stages"]["disk"] = cp
        _save_state(state_path, state)
        return {"verdict": "BLOCKED", "stage": "disk", "state": state}

    for stage in STAGES:
        cp = state["stages"].get(stage)
        resumed = False
        if cp and cp.get("status") == "OK":
            stored_hash = cp.get("output_hash")
            recorded_outputs = cp.get("outputs")
            if stored_hash and recorded_outputs is not None \
                    and stored_hash != _hash_obj(recorded_outputs):
                pass  # corrupt checkpoint hash -> re-execute below
            else:
                resumed = True
        if resumed:
            cp["resumed"] = True
            state["stages"][stage] = cp
            continue

        slice_dir(topic_id).mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        disk_before = disk_free_bytes(state_path.parent)
        try:
            result = stages[stage](topic_id, state) or {}
            status = result.get("status", "BLOCKED")
        except Exception as exc:  # fail-closed on any stage crash
            status = "BLOCKED"
            result = {"error": f"{type(exc).__name__}: {exc}"}
        wall = round(time.time() - t0, 3)
        disk_after = disk_free_bytes(state_path.parent)
        outputs = result.get("outputs", {})
        cp = {
            "status": status,
            "started_at": iso_now(),
            "finished_at": iso_now(),
            "wall_time_s": wall,
            "disk_before_bytes": disk_before,
            "disk_after_bytes": disk_after,
            "outputs": outputs,
            "output_hash": _hash_obj(outputs),
            "error": result.get("error"),
        }
        state["stages"][stage] = cp
        _save_state(state_path, state)
        if status != "OK":
            return {"verdict": "BLOCKED", "stage": stage, "state": state}

    return {"verdict": "OK", "state": state}


# ---------------------------------------------------------------------------
# Chapter mode (Milestone Z4)
# ---------------------------------------------------------------------------
def _estimate_sentence_duration(sentence):
    """Rough narration duration: ~2.5 words/sec + 0.3s breath per sentence."""
    words = len([w for w in sentence.split() if w.strip()])
    return max(2.0, words / 2.5 + 0.3)


def split_script_into_chapters(script_path, max_duration_s=MAX_CHAPTER_DURATION):
    """Split a script markdown into chapters, each <= max_duration_s narration."""
    sentences = [row["sentence"] for row in _parse_script_rows(script_path)]

    chapters = []
    current = []
    current_dur = 0.0
    chapter_index = 0
    for sentence in sentences:
        dur = _estimate_sentence_duration(sentence)
        if current and current_dur + dur > max_duration_s:
            chapters.append({
                "chapter_index": chapter_index,
                "sentences": list(current),
                "duration_s": round(current_dur, 3),
            })
            chapter_index += 1
            current = []
            current_dur = 0.0
        current.append(sentence)
        current_dur += dur
    if current:
        chapters.append({
            "chapter_index": chapter_index,
            "sentences": list(current),
            "duration_s": round(current_dur, 3),
        })
    return chapters


def _chapter_script_path(state_root, topic_id, chapter_index):
    return Path(state_root) / topic_id / f"chapter_{chapter_index}.md"


def _write_chapter_script(state_root, topic_id, chapter_index, sentences):
    path = _chapter_script_path(state_root, topic_id, chapter_index)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["| Beat | Sentence | claim_ids | flags |", "|---|---|---|---|"]
    for i, s in enumerate(sentences, 1):
        lines.append(f"| B{chapter_index + 1}-{i} | {s} | CH-{chapter_index + 1}-{i} | |")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _extract_video_path(result):
    """Pull a video path out of a run_pipeline result dict."""
    state = result.get("state", {})
    stages = state.get("stages", {})
    for stage_name in ("render", "edl", "narration", "subtitles"):
        stage = stages.get(stage_name, {})
        outputs = stage.get("outputs", {})
        if isinstance(outputs, dict) and outputs.get("video"):
            return outputs["video"]
    return None


def concatenate_chapters(videos, output_path, crossfade_duration_s=1.0):
    """Concatenate chapter videos with crossfades using ffmpeg xfade filter."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if len(videos) == 1:
        import shutil
        shutil.copy2(videos[0], output_path)
        return {"status": "OK", "outputs": {"video": str(output_path)}}
    if crossfade_duration_s <= 0:
        lst = output_path.parent / "chapter_concat.txt"
        lst.write_text("\n".join(f"file '{v}'" for v in videos), encoding="utf-8")
        _ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(output_path)])
        return {"status": "OK", "outputs": {"video": str(output_path)}}
    # Build xfade filter chain: each crossfade overlaps the end of prev with start of next
    inputs = []
    filter_parts = []
    for i, v in enumerate(videos):
        inputs.extend(["-i", str(v)])
    # Start with first video
    prev_label = f"[{0}:v]"
    prev_audio = f"[{0}:a]"
    total_dur = 0.0
    # Probe durations to place crossfades
    durations = []
    for v in videos:
        res = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                              "-show_format", str(v)], capture_output=True, text=True)
        d = float(json.loads(res.stdout)["format"]["duration"])
        durations.append(d)
    offset = 0.0
    for i in range(1, len(videos)):
        xfade_start = offset + durations[i - 1] - crossfade_duration_s
        filter_parts.append(
            f"{prev_label}[{i}:v]xfade=transition=fade:duration={crossfade_duration_s}:offset={xfade_start}[v{i}];"
            f"{prev_audio}[{i}:a]acrossfade=d={crossfade_duration_s}[a{i}];"
        )
        prev_label = f"[v{i}]"
        prev_audio = f"[a{i}]"
        offset += durations[i - 1]
    filter_str = "".join(filter_parts) + f"{prev_label},format=yuv420p[v];{prev_audio}[a]"
    _ffmpeg(inputs + ["-filter_complex", filter_str, "-map", "[v]", "-map", "[a]",
                      "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30",
                      "-c:a", "aac", "-b:a", "192k", str(output_path)])
    return {"status": "OK", "outputs": {"video": str(output_path)}}


def final_loudness_pass(video_path):
    """Run finish_audio-style loudnorm on the final video's audio."""
    from tools.audio.finish_audio import FinishAudioTool  # noqa: WPS433
    video_path = Path(video_path)
    wav_tmp = video_path.parent / (video_path.stem + "_audio.wav")
    out_tmp = video_path.parent / (video_path.stem + "_loud.wav")
    # Extract audio
    _ffmpeg(["-i", str(video_path), "-vn", "-acodec", "pcm_s16le", "-ar", "44100",
             "-ac", "2", str(wav_tmp)])
    result = FinishAudioTool().execute({"input_path": str(wav_tmp), "output_path": str(out_tmp)})
    if not result.success:
        return {"status": "BLOCKED", "error": f"final loudness pass failed: {result.error}"}
    # Remux video with new audio
    final = video_path.parent / (video_path.stem + "_final.mp4")
    _ffmpeg(["-i", str(video_path), "-i", str(out_tmp), "-c:v", "copy", "-c:a", "aac",
             "-b:a", "192k", "-shortest", str(final)])
    wav_tmp.unlink(missing_ok=True)
    out_tmp.unlink(missing_ok=True)
    return {"status": "OK", "outputs": {"video": str(final)}, "loudness": result.data}


def run_chapter_mode(topic_id, script_path=None, chapters=None, max_chapter_duration_s=None,
                     state_path=None, state_root=None, stages=None):
    """Run the full pipeline per chapter, then concatenate with crossfades + final loudness."""
    if stages is None:
        stages = STAGE_REGISTRY
    if state_path is None:
        state_root = Path(state_root) if state_root else ROOT / "docs/openmontage/slice"
        state_path = Path(state_root) / topic_id / "chapter_state.json"
    state_path = Path(state_path)

    if max_chapter_duration_s is None:
        max_chapter_duration_s = MAX_CHAPTER_DURATION

    if chapters is None:
        if script_path is None:
            return {"verdict": "BLOCKED", "error": "need script_path or chapters"}
        chapters = split_script_into_chapters(script_path, max_chapter_duration_s)

    state = {"topic_id": topic_id, "chapters": chapters, "updated_at": iso_now(),
             "stages": {}}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["topic_id"] = topic_id
        state["updated_at"] = iso_now()
        state.setdefault("stages", {})

    # Global disk budget
    if disk_free_bytes(state_path.parent) < MIN_FREE_BYTES:
        cp = {"status": "BLOCKED", "started_at": iso_now(), "finished_at": iso_now(),
              "wall_time_s": 0.0, "disk_before_bytes": disk_free_bytes(state_path.parent),
              "disk_after_bytes": disk_free_bytes(state_path.parent), "outputs": {},
              "output_hash": _hash_obj({}),
              "error": f"free disk below {MIN_FREE_BYTES} bytes"}
        state["stages"]["disk"] = cp
        _save_state(state_path, state)
        return {"verdict": "BLOCKED", "stage": "disk", "state": state}

    chapter_videos = []
    any_executed = False
    for ch in chapters:
        ci = ch["chapter_index"]
        cp = state["stages"].get(f"chapter_{ci}")
        if cp and cp.get("status") == "OK":
            stored_hash = cp.get("output_hash")
            recorded_outputs = cp.get("outputs")
            if stored_hash and recorded_outputs is not None \
                    and stored_hash != _hash_obj(recorded_outputs):
                pass  # corrupt -> re-run
            else:
                cp["resumed"] = True
                state["stages"][f"chapter_{ci}"] = cp
                chapter_videos.append(cp["outputs"].get("video"))
                continue

        # Per-chapter disk budget
        if disk_free_bytes(state_path.parent) < MIN_FREE_BYTES:
            cp = {"status": "BLOCKED", "started_at": iso_now(), "finished_at": iso_now(),
                  "wall_time_s": 0.0,
                  "disk_before_bytes": disk_free_bytes(state_path.parent),
                  "disk_after_bytes": disk_free_bytes(state_path.parent), "outputs": {},
                  "output_hash": _hash_obj({}),
                  "error": f"free disk below {MIN_FREE_BYTES} bytes before chapter {ci}"}
            state["stages"][f"chapter_{ci}"] = cp
            _save_state(state_path, state)
            return {"verdict": "BLOCKED", "stage": "disk", "chapter": ci, "state": state}

        chapter_script = _write_chapter_script(Path(state_path).parent, topic_id, ci,
                                               ch["sentences"])
        t0 = time.time()
        disk_before = disk_free_bytes(state_path.parent)
        try:
            result = run_pipeline(topic_id, state_path=state_path,
                                  stages=stages,
                                  initial_state={
                                      "topic_id": topic_id, "chapter_index": ci,
                                      "chapter_script": str(chapter_script),
                                      "chapters": chapters,
                                  })
            status = result.get("verdict", "BLOCKED")
        except Exception as exc:  # fail-closed
            status = "BLOCKED"
            result = {"error": f"{type(exc).__name__}: {exc}"}
        wall = round(time.time() - t0, 3)
        disk_after = disk_free_bytes(state_path.parent)
        video_path = _extract_video_path(result)
        cp = {
            "status": status,
            "chapter_index": ci,
            "started_at": iso_now(),
            "finished_at": iso_now(),
            "wall_time_s": wall,
            "disk_before_bytes": disk_before,
            "disk_after_bytes": disk_after,
            "outputs": {"video": video_path, "duration_s": ch["duration_s"]},
            "output_hash": _hash_obj({"video": video_path, "duration_s": ch["duration_s"]}),
            "error": result.get("error"),
        }
        state["stages"][f"chapter_{ci}"] = cp
        _save_state(state_path, state)
        if status != "OK":
            return {"verdict": "BLOCKED", "stage": f"chapter_{ci}", "chapter": ci, "state": state}
        chapter_videos.append(video_path)
        any_executed = True

    # Skip concat+loudness if all chapters were resumed and already done
    concat_cp = state["stages"].get("concatenate")
    loud_cp = state["stages"].get("final_loudness")
    if not any_executed and concat_cp and concat_cp.get("status") == "OK" \
            and loud_cp and loud_cp.get("status") == "OK":
        return {"verdict": "OK", "state": state,
                "final_video": loud_cp["outputs"]["video"]}

    # Concatenate with crossfades
    concat_out = Path(state_path).parent / f"final_{topic_id}_chapters.mp4"
    concat_res = concatenate_chapters(chapter_videos, concat_out, crossfade_duration_s=1.0)
    if concat_res["status"] != "OK":
        return {"verdict": "BLOCKED", "stage": "concatenate", "state": state}

    # Final loudness pass
    loud_res = final_loudness_pass(concat_out)
    if loud_res["status"] != "OK":
        return {"verdict": "BLOCKED", "stage": "final_loudness", "state": state}

    state["stages"]["concatenate"] = {"status": "OK", "outputs": {"video": str(concat_out)}}
    state["stages"]["final_loudness"] = {"status": "OK", "outputs": {"video": loud_res["outputs"]["video"]}}
    _save_state(state_path, state)
    return {"verdict": "OK", "state": state, "final_video": loud_res["outputs"]["video"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="One-command episode pipeline (Z3/Z4)")
    parser.add_argument("topic_id", help="topic id, e.g. artemis")
    parser.add_argument("--chapters", action="store_true",
                        help="run chapter mode: split script into <=6 min chapters")
    args = parser.parse_args(argv)
    if args.chapters:
        script = topic_script(args.topic_id)
        if not script:
            print(json.dumps({"verdict": "BLOCKED", "error": f"no script for {args.topic_id}"}))
            return 1
        res = run_chapter_mode(args.topic_id, script_path=script)
    else:
        res = run_pipeline(args.topic_id)
    print(json.dumps({"verdict": res["verdict"], "stage": res.get("stage"),
                      "state": res["state"]}, indent=2))
    return res.get("exit_code", 0 if res["verdict"] == "OK" else 1)


if __name__ == "__main__":
    sys.exit(main())
