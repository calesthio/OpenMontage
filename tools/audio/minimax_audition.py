"""Batch audition helper for MiniMax Speech voices.

This module is intentionally a small CLI wrapper around MiniMaxTTS rather than
a BaseTool. OpenMontage discovers provider tools automatically, and this helper
exists only to make voice selection practical when MiniMax's static voice list
does not include audio previews.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

from tools.audio.minimax_tts import MiniMaxTTS


DEFAULT_MANDARIN_VOICES = [
    "Chinese (Mandarin)_Reliable_Executive",
    "Chinese (Mandarin)_News_Anchor",
    "Chinese (Mandarin)_Male_Announcer",
    "Chinese (Mandarin)_Radio_Host",
    "Chinese (Mandarin)_Gentleman",
    "Chinese (Mandarin)_Warm_Bestie",
    "Chinese (Mandarin)_Sincere_Adult",
    "Chinese (Mandarin)_Mature_Woman",
]

DEFAULT_TEXT = (
    "这个工具不是替你写一个结论，而是把日志、链路、订单和上下文串起来，"
    "让排查过程从凭经验，变成可复盘的工作流。"
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    text = load_text(args)
    tool = MiniMaxTTS()
    voices = list(resolve_voices(args, tool))
    output_dir = resolve_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    failures = []

    for index, voice_id in enumerate(voices, start=1):
        stem = f"{index:02d}-{slugify(voice_id)}"
        audio_path = output_dir / f"{stem}.{args.format}"
        metadata_path = output_dir / f"{stem}.{args.format}.json"
        result = tool.execute(
            {
                "text": text,
                "voice_id": voice_id,
                "model": args.model,
                "language_boost": args.language_boost,
                "speed": args.speed,
                "vol": args.vol,
                "pitch": args.pitch,
                "format": args.format,
                "sample_rate": args.sample_rate,
                "bitrate": args.bitrate,
                "channel": args.channel,
                "subtitle_enable": args.subtitle_enable,
                "subtitle_type": args.subtitle_type,
                "output_path": str(audio_path),
                "metadata_path": str(metadata_path),
            }
        )
        if result.success:
            rows.append(
                {
                    "voice_id": voice_id,
                    "audio": audio_path,
                    "metadata": metadata_path,
                    "duration": result.data.get("audio_duration_seconds"),
                    "trace_id": result.data.get("trace_id"),
                }
            )
        else:
            failures.append({"voice_id": voice_id, "error": result.error or "unknown error"})
            if not args.continue_on_error:
                break

    review_path = output_dir / "AUDITION_REVIEW.md"
    review_path.write_text(render_review(args, text, rows, failures), encoding="utf-8")
    print(f"MiniMax audition review: {review_path}")
    return 1 if failures else 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a MiniMax Speech voice audition pack.")
    parser.add_argument("--text", help="Short audition text. Defaults to a Mandarin product-narration sample.")
    parser.add_argument("--text-file", type=Path, help="Read audition text from a UTF-8 text file.")
    parser.add_argument(
        "--voices",
        nargs="+",
        help="Voice IDs to audition. Defaults to a practical Mandarin shortlist.",
    )
    parser.add_argument("--output-dir", type=Path, help="Directory for generated audio and review markdown.")
    parser.add_argument("--model", default="speech-2.8-hd")
    parser.add_argument("--language-boost", default="Chinese")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--vol", type=float, default=1.0)
    parser.add_argument("--pitch", type=int, default=0)
    parser.add_argument("--format", choices=["mp3", "wav", "flac"], default="mp3")
    parser.add_argument("--sample-rate", type=int, default=32000)
    parser.add_argument("--bitrate", type=int, default=128000)
    parser.add_argument("--channel", type=int, choices=[1, 2], default=1)
    parser.add_argument("--subtitle-enable", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--subtitle-type", choices=["sentence", "word"], default="sentence")
    parser.add_argument(
        "--discover-voices",
        action="store_true",
        help="Fetch account-available voices from MiniMax Get Voice before auditioning.",
    )
    parser.add_argument(
        "--voice-type",
        choices=["system", "voice_cloning", "voice_generation", "all"],
        default="system",
        help="Voice category to fetch when --discover-voices is set.",
    )
    parser.add_argument(
        "--language-filter",
        default="Chinese (Mandarin)",
        help="Only audition discovered voices whose voice_id contains this text. Use an empty string to disable.",
    )
    parser.add_argument(
        "--max-voices",
        type=int,
        default=8,
        help="Maximum number of discovered voices to audition.",
    )
    parser.add_argument("--continue-on-error", action="store_true")
    return parser.parse_args(argv)


def load_text(args: argparse.Namespace) -> str:
    if args.text_file:
        return args.text_file.read_text(encoding="utf-8").strip()
    return (args.text or DEFAULT_TEXT).strip()


def resolve_voices(args: argparse.Namespace, tool: MiniMaxTTS) -> Iterable[str]:
    if args.voices:
        return args.voices
    if not args.discover_voices:
        return DEFAULT_MANDARIN_VOICES

    payload = tool.list_voices(args.voice_type)
    candidates = []
    voice_keys = ["system_voice", "voice_cloning", "voice_generation"]
    for key in voice_keys:
        for item in payload.get(key, []) or []:
            voice_id = item.get("voice_id")
            if not voice_id:
                continue
            if args.language_filter and args.language_filter not in voice_id:
                continue
            candidates.append(voice_id)
    return candidates[: args.max_voices]


def resolve_output_dir(output_dir: Path | None) -> Path:
    if output_dir:
        return output_dir
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path("projects/minimax-tts-audition/assets/audio") / stamp


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-").lower()
    return slug or "voice"


def render_review(
    args: argparse.Namespace,
    text: str,
    rows: list[dict[str, object]],
    failures: list[dict[str, str]],
) -> str:
    lines = [
        "# MiniMax TTS Audition Review",
        "",
        "## Settings",
        "",
        f"- Model: `{args.model}`",
        f"- Language boost: `{args.language_boost}`",
        f"- Speed: `{args.speed}`",
        f"- Pitch: `{args.pitch}`",
        f"- Format: `{args.format}`",
        f"- Subtitle type: `{args.subtitle_type}`",
        "",
        "## Audition Text",
        "",
        text,
        "",
        "## Voice Candidates",
        "",
        "| Voice ID | Duration | Audio | Metadata | Trace ID | Notes |",
        "|---|---:|---|---|---|---|",
    ]
    for row in rows:
        duration = row["duration"]
        duration_text = f"{duration:.2f}s" if isinstance(duration, (int, float)) else ""
        audio = Path(str(row["audio"]))
        metadata = Path(str(row["metadata"]))
        lines.append(
            "| "
            f"`{row['voice_id']}` | "
            f"{duration_text} | "
            f"[audio]({audio.name}) | "
            f"[json]({metadata.name}) | "
            f"`{row.get('trace_id') or ''}` |  |"
        )

    if failures:
        lines.extend(["", "## Failures", ""])
        for failure in failures:
            lines.append(f"- `{failure['voice_id']}`: {failure['error']}")

    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
