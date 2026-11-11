"""ElevenLabs video-conditioned soundtracks, including safe stem ZIP ingestion."""

import io
import mimetypes
import zipfile
from contextlib import ExitStack
from pathlib import Path, PurePosixPath
import requests
from tools.audio._speech_api import SpeechAPI
from tools.base_tool import ToolResult


class ElevenLabsSoundtrack(SpeechAPI):
    name = "elevenlabs_soundtrack"
    capability = "music_generation"
    capabilities = ["video_to_music", "synchronized_sound_effects", "separate_tracks"]
    provider = "elevenlabs"
    credential = "ELEVENLABS_API_KEY"
    dependencies = ["env:ELEVENLABS_API_KEY"]
    install_instructions = "Configure ELEVENLABS_API_KEY with video-to-music access."
    input_schema = {
        "type": "object",
        "required": ["video_paths"],
        "properties": {
            "video_paths": {
                "type": "array",
                "minItems": 1,
                "maxItems": 10,
                "items": {"type": "string"},
            },
            "description": {"type": "string"},
            "tags": {"type": "array", "maxItems": 10, "items": {"type": "string"}},
            "add_sfx": {"type": "boolean"},
            "separate_tracks": {"type": "boolean"},
            "use_audio_as_reference": {"type": "boolean"},
            "model_id": {"enum": ["music_v1", "music_v2", "music_v2_5"]},
            "output_path": {"type": "string"},
        },
    }

    def generate(self, inputs, key):
        paths = [Path(p) for p in inputs["video_paths"]]
        if sum(p.stat().st_size for p in paths) > 200 * 1024 * 1024:
            raise ValueError("Videos exceed combined 200 MB limit")
        if any(p.stat().st_size == 0 for p in paths):
            raise ValueError("Empty video")
        from tools.video._shared import probe_output

        durations = [probe_output(p).get("duration_seconds") for p in paths]
        if all(d is not None for d in durations) and sum(durations) > 600:
            raise ValueError("Videos exceed combined 600 second limit")
        data = [
            (k, str(inputs[k]).lower())
            for k in ("add_sfx", "separate_tracks", "use_audio_as_reference")
            if k in inputs
        ]
        data.extend((k, inputs[k]) for k in ("description", "model_id") if k in inputs)
        data.extend(("tags", tag) for tag in inputs.get("tags", []))
        with ExitStack() as stack:
            files = [
                (
                    "videos[]",
                    (
                        p.name,
                        stack.enter_context(p.open("rb")),
                        mimetypes.guess_type(p)[0] or "video/mp4",
                    ),
                )
                for p in paths
            ]
            r = requests.post(
                "https://api.elevenlabs.io/v1/music/video-to-music",
                headers={"xi-api-key": key},
                data=data,
                files=files,
                params={"output_format": "mp3_44100_128"},
                timeout=600,
            )
        r.raise_for_status()
        if not inputs.get("separate_tracks"):
            return self.save_audio(
                inputs,
                r.content,
                model=inputs.get("model_id", "service-default"),
                suffix=".mp3",
            )
        out = Path(inputs.get("output_path") or "soundtrack.mp3")
        folder = out.with_name(out.stem + "_tracks")
        outputs = []
        with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
            entries = [x for x in archive.infolist() if not x.is_dir()]
            if not entries or sum(x.file_size for x in entries) > 500 * 1024 * 1024:
                raise ValueError("Invalid or oversized stem archive")
            names = set()
            for entry in entries:
                path = PurePosixPath(entry.filename.replace("\\", "/"))
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or ":" in entry.filename
                    or path.suffix.lower() not in {".mp3", ".wav", ".flac"}
                ):
                    raise ValueError("Unsafe or unsupported stem archive entry")
                if path.name in names:
                    raise ValueError("Duplicate stem filename")
                names.add(path.name)
            folder.mkdir(parents=True, exist_ok=True)
            for entry in entries:
                dest = folder / PurePosixPath(entry.filename.replace("\\", "/")).name
                dest.write_bytes(archive.read(entry))
                outputs.append(str(dest))
        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": inputs.get("model_id", "service-default"),
                "outputs": outputs,
                "tracks": outputs,
                "cost_status": "unquoted",
            },
            artifacts=outputs,
            cost_usd=None,
        )
