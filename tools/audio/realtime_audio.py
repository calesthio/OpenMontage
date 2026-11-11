"""Realtime speech sessions, isolated from the narration selector."""

import base64
import io
import json
import os
import wave
from pathlib import Path
from tools.audio._speech_api import SpeechAPI
from tools.audio._realtime_session import RealtimeAudioSession
from tools.base_tool import ToolResult, ToolStatus


class RealtimeAudio(SpeechAPI):
    name = "realtime_audio"
    provider = "realtime_audio"
    capability = "realtime_audio"
    capabilities = [
        "speech_to_speech",
        "streaming_transcription",
        "tool_events",
        "cancellation",
    ]
    credential = "XAI_API_KEY"
    dependencies = ["python:websockets"]
    install_instructions = "Configure XAI_API_KEY, ELEVENLABS_API_KEY, or MAI_API_KEY + MAI_ENDPOINT + MAI_TRANSCRIBE_DEPLOYMENT for the selected provider."
    input_schema = {
        "type": "object",
        "required": ["provider", "model"],
        "properties": {
            "provider": {"enum": ["grok", "elevenlabs", "microsoft_mai"]},
            "model": {
                "enum": [
                    "grok-voice-3.0",
                    "grok-voice-latest",
                    "eleven_realtime_v1_mini",
                    "eleven_realtime_v1_max",
                    "MAI-Transcribe-2-Streaming",
                ]
            },
            "text": {"type": "string"},
            "audio_path": {"type": "string"},
            "voice_id": {"type": "string"},
            "instructions": {"type": "string"},
            "tools": {"type": "array", "items": {"type": "object"}},
            "timeout": {"type": "number", "exclusiveMinimum": 0, "maximum": 3600},
            "output_path": {"type": "string"},
        },
    }

    def get_status(self):
        return (
            ToolStatus.AVAILABLE
            if os.getenv("XAI_API_KEY")
            or os.getenv("ELEVENLABS_API_KEY")
            or all(
                os.getenv(k)
                for k in ("MAI_API_KEY", "MAI_ENDPOINT", "MAI_TRANSCRIBE_DEPLOYMENT")
            )
            else ToolStatus.UNAVAILABLE
        )

    def execute(self, inputs):
        from jsonschema import validate

        try:
            validate(inputs, self.input_schema)
            return self.generate(inputs, None)
        except Exception as exc:
            return ToolResult(success=False, error=f"Realtime session failed: {exc}")

    def generate(self, inputs, key):
        provider = inputs["provider"]
        transcribe = provider == "microsoft_mai"
        if inputs.get("tools"):
            raise ValueError(
                "Use RealtimeAudioSession for tool calls; the file runner closes after one response"
            )
        if bool(inputs.get("text")) == bool(inputs.get("audio_path")):
            raise ValueError("Supply exactly one text or audio_path")
        if transcribe and not inputs.get("audio_path"):
            raise ValueError("MAI requires audio input")
        suffix = ".json" if transcribe else ".wav"
        out = Path(inputs.get("output_path") or "realtime_output" + suffix)
        if out.suffix.lower() != suffix:
            raise ValueError("output_path must end in " + suffix)
        pcm = None
        rate = 24000
        if inputs.get("audio_path"):
            with wave.open(inputs["audio_path"], "rb") as audio:
                rate = audio.getframerate()
                if (
                    audio.getnchannels() != 1
                    or audio.getsampwidth() != 2
                    or rate not in {16000, 24000}
                ):
                    raise ValueError("Input must be mono PCM16 WAV at 16 or 24 kHz")
                if audio.getnframes() / rate > 600:
                    raise ValueError(
                        "File runner accepts at most 10 minutes; use RealtimeAudioSession for live streams"
                    )
                pcm = audio.readframes(audio.getnframes())
        events = []
        chunks = []
        completed = False
        with RealtimeAudioSession(
            provider,
            inputs["model"],
            voice=inputs.get("voice_id"),
            instructions=inputs.get("instructions", ""),
            tools=None,
            timeout=inputs.get("timeout", 180),
            sample_rate=rate,
            pacing="bursty",
        ) as session:
            import threading

            sender_errors = []

            def send_input():
                try:
                    if pcm is not None:
                        for offset in range(0, len(pcm), rate * 2):
                            session.append_audio(pcm[offset : offset + rate * 2])
                        session.commit()
                    else:
                        session.send(
                            {
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "user",
                                    "content": [
                                        {"type": "input_text", "text": inputs["text"]}
                                    ],
                                },
                            }
                        )
                    if not transcribe:
                        session.request_response()
                except Exception as exc:
                    sender_errors.append(exc)
                    session.socket.close()

            sender = threading.Thread(target=send_input, daemon=True)
            sender.start()
            while True:
                event = session.receive()
                kind = event.get("type") or ""
                if kind in {"response.output_audio.delta", "response.audio.delta"}:
                    chunks.append(base64.b64decode(event["delta"], validate=True))
                    events.append({"type": kind, "bytes": len(chunks[-1])})
                elif kind.startswith("session."):
                    # Do not persist session configuration, credentials or connection metadata.
                    continue
                else:
                    events.append(event)
                if (
                    transcribe
                    and kind == "conversation.item.input_audio_transcription.completed"
                ):
                    completed = True
                    break
                if kind == "response.done":
                    status = event.get("response", {}).get("status", "completed")
                    if status != "completed":
                        raise ValueError("Realtime response ended with " + status)
                    completed = True
                    break
            sender.join(timeout=5)
            if sender_errors:
                raise sender_errors[0]
            if sender.is_alive():
                raise TimeoutError("Realtime input sender did not finish")
        if not completed:
            raise ValueError("Realtime response incomplete")
        out.parent.mkdir(parents=True, exist_ok=True)
        if transcribe:
            out.write_text(
                json.dumps(events, ensure_ascii=False, indent=2), encoding="utf8"
            )
            artifacts = [str(out)]
        else:
            if not chunks:
                raise ValueError("Realtime response returned no audio")
            with wave.open(str(out), "wb") as writer:
                writer.setnchannels(1)
                writer.setsampwidth(2)
                writer.setframerate(rate)
                writer.writeframes(b"".join(chunks))
            sidecar = out.with_name(out.name + ".events.json")
            sidecar.write_text(
                json.dumps(events, ensure_ascii=False, indent=2), encoding="utf8"
            )
            artifacts = [str(out), str(sidecar)]
        return ToolResult(
            success=True,
            data={
                "output": str(out),
                "provider": provider,
                "model": inputs["model"],
                "events": events,
                "cost_status": "unquoted",
            },
            artifacts=artifacts,
            model=inputs["model"],
            cost_usd=None,
        )
