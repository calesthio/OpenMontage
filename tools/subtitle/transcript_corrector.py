"""Azerbaijani-aware transcript correction with a human review gate.

Runs between the transcriber and caption generation:

1. Unicode repair: NFC, Cyrillic/Latin schwa look-alikes, stray spaces
   before punctuation (lib.az_text.normalize).
2. Lexicon replacements: shared Azerbaijani lexicon plus the client's own
   names, brands and terms (lib.reels_profiles.load_lexicon). Matching is
   case- and punctuation-insensitive with Azerbaijani I/ı/İ/i rules, works on
   multi-word phrases, and keeps word timings.
3. Review flags: every word below ``review_threshold`` ASR probability, and
   every replacement made, is listed for a human. The output is marked
   ``verified: false`` until someone approves it; the tool never declares a
   transcript correct on its own.
"""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

from lib import az_text
from lib.reels_profiles import ProfileError, load_lexicon
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolTier,
)


def _phrase_table(replacements: dict[str, str]) -> list[tuple[list[str], str]]:
    """Longest phrases first so "sosial media" wins over "media"."""
    table = []
    for wrong, right in replacements.items():
        key = [az_text.match_key(tok) for tok in wrong.split()]
        key = [k for k in key if k]
        if key:
            table.append((key, right))
    table.sort(key=lambda item: len(item[0]), reverse=True)
    return table


class TranscriptCorrector(BaseTool):
    name = "transcript_corrector"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "subtitle"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = []  # pure Python
    install_instructions = "No external dependencies required."

    capabilities = ["transcript_correction", "az_orthography", "review_flags"]

    input_schema = {
        "type": "object",
        "properties": {
            "transcript_path": {
                "type": "string",
                "description": "Transcriber JSON (with segments and words).",
            },
            "segments": {
                "type": "array",
                "description": "Transcript segments, used when transcript_path is omitted.",
            },
            "client_id": {
                "type": "string",
                "description": "Loads brand_profiles/<client_id>/corrections.yaml on top of the shared lexicon.",
            },
            "replacements": {
                "type": "object",
                "description": "Extra one-off replacements {wrong: right}; win over lexicon files.",
            },
            "review_threshold": {
                "type": "number",
                "default": 0.6,
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Words with ASR probability below this are flagged for review.",
            },
            "output_path": {"type": "string"},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "segments": {"type": "array"},
            "changes": {"type": "array"},
            "review_items": {"type": "array"},
            "verified": {"type": "boolean"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=5)
    idempotency_key_fields = ["transcript_path", "segments", "client_id", "replacements", "review_threshold"]
    side_effects = ["writes corrected transcript JSON to output_path"]
    user_visible_verification = [
        "Read every review item against the audio before approving captions",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()

        source = None
        if inputs.get("transcript_path"):
            source = Path(inputs["transcript_path"])
            if not source.is_file():
                return ToolResult(success=False, error=f"Transcript not found: {source}")
            transcript = json.loads(source.read_text(encoding="utf-8"))
        elif inputs.get("segments") is not None:
            transcript = {"segments": inputs["segments"]}
        else:
            return ToolResult(success=False, error="Provide transcript_path or segments")

        try:
            lexicon = load_lexicon(inputs.get("client_id"))
        except ProfileError as exc:
            return ToolResult(success=False, error=str(exc))
        lexicon["replacements"].update(inputs.get("replacements") or {})

        threshold = float(inputs.get("review_threshold", 0.6))
        segments, changes, review = self.correct_segments(
            transcript.get("segments") or [], lexicon["replacements"], threshold,
            protected=set(lexicon["protected_terms"]),
        )

        result = {
            **{k: v for k, v in transcript.items() if k not in {"segments", "word_timestamps"}},
            "segments": segments,
            "word_timestamps": [w for s in segments for w in s.get("words", [])],
            "changes": changes,
            "review_items": review,
            "verified": False,
            "client_id": inputs.get("client_id"),
        }

        output_path = inputs.get("output_path")
        if not output_path and source is not None:
            output_path = str(source.with_name(source.stem + "_corrected.json"))
        artifacts = []
        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            artifacts.append(str(out))

        return ToolResult(
            success=True,
            data={
                **result,
                "output": output_path,
                "change_count": len(changes),
                "review_count": len(review),
            },
            artifacts=artifacts,
            duration_seconds=round(time.time() - start, 3),
        )

    @staticmethod
    def correct_segments(
        segments: list[dict], replacements: dict[str, str], threshold: float,
        protected: set[str] | None = None,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        table = _phrase_table(replacements)
        protected = protected or set()
        segments = copy.deepcopy(segments)
        changes: list[dict] = []
        review: list[dict] = []

        for seg in segments:
            words = seg.get("words") or []
            if not words:
                # Segment without word timings: correct the text only.
                tokens = [{"word": t} for t in az_text.normalize(seg.get("text", "")).split()]
                tokens = TranscriptCorrector._replace_in_words(tokens, table, changes, seg, protected)
                seg["text"] = " ".join(t["word"] for t in tokens)
                continue

            for w in words:
                w["word"] = az_text.normalize(w.get("word", ""))
            words = [w for w in words if w["word"]]
            words = TranscriptCorrector._replace_in_words(words, table, changes, seg, protected)

            for w in words:
                prob = w.get("probability")
                if prob is not None and prob < threshold and not w.get("corrected"):
                    review.append({
                        "segment_id": seg.get("id"),
                        "word": w["word"],
                        "start": w.get("start"),
                        "end": w.get("end"),
                        "probability": prob,
                        "reason": "low_confidence",
                    })
            seg["words"] = words
            seg["text"] = az_text.normalize(" ".join(w["word"] for w in words))

        for change in changes:
            review.append({**change, "word": change["to"], "reason": "lexicon_replacement"})
        return segments, changes, review

    @staticmethod
    def _replace_in_words(
        words: list[dict], table: list[tuple[list[str], str]], changes: list[dict], seg: dict,
        protected: set[str] | None = None,
    ) -> list[dict]:
        keys = [az_text.match_key(w["word"]) for w in words]
        out: list[dict] = []
        i = 0
        while i < len(words):
            for phrase, right in table:
                n = len(phrase)
                if keys[i:i + n] != phrase:
                    continue
                span = words[i:i + n]
                original = " ".join(w["word"] for w in span)
                lead = az_text.strip_punct(span[0]["word"])[0]
                trail = az_text.strip_punct(span[-1]["word"])[2]
                fixed = az_text.apply_case_like(
                    az_text.strip_punct(span[0]["word"])[1], right,
                    protected=right in (protected or ()),
                )
                new_text = f"{lead}{fixed}{trail}"
                if new_text != original:
                    changes.append({
                        "segment_id": seg.get("id"),
                        "from": original,
                        "to": new_text,
                        "start": span[0].get("start"),
                        "end": span[-1].get("end"),
                    })
                right_tokens = new_text.split()
                if len(right_tokens) == n:
                    for w, tok in zip(span, right_tokens):
                        out.append({**w, "word": tok, "corrected": tok != w["word"] or w.get("corrected", False)})
                else:
                    merged = {**span[0], "word": new_text, "corrected": True}
                    if "end" in span[-1]:
                        merged["end"] = span[-1]["end"]
                    probs = [w["probability"] for w in span if w.get("probability") is not None]
                    if probs:
                        merged["probability"] = min(probs)
                    out.append(merged)
                i += n
                break
            else:
                out.append(words[i])
                i += 1
        return out
