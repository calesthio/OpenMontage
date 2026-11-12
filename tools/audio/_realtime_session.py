"""Bounded realtime audio transport. Callers own turns and tool execution."""

from __future__ import annotations
import base64
import json
import os
import time
from urllib.parse import urlparse, urlencode
import requests
from websockets.sync.client import connect


class RealtimeAudioSession:
    """Context-managed bidirectional client; never executes received tool calls.

    send/receive expose provider events for live callers. cancel interrupts a
    response; submit_tool_result returns a caller-approved function result.
    Secrets stay in memory and are never returned or persisted.
    """

    def __init__(
        self,
        provider,
        model,
        *,
        voice=None,
        instructions="",
        tools=None,
        turn_detection=None,
        timeout=180,
        sample_rate=24000,
        pacing="realtime",
    ):
        if not 0 < timeout <= 3600:
            raise ValueError("timeout must be 1-3600 seconds")
        if sample_rate not in {16000, 24000}:
            raise ValueError("PCM sample rate must be 16000 or 24000")
        self.provider = provider
        self.model = model
        self.timeout = timeout
        self.sample_rate = sample_rate
        self.socket = None
        self.deadline = None
        pcm = {"type": "audio/pcm", "rate": sample_rate}
        if provider == "grok":
            if model not in {"grok-voice-3.0", "grok-voice-latest"}:
                raise ValueError("Unsupported Grok voice model")
            self.url = "wss://api.x.ai/v1/realtime?" + urlencode({"model": model})
            self.headers = {"Authorization": "Bearer " + os.environ["XAI_API_KEY"]}
            self.session = {
                "voice": voice or "eve",
                "instructions": instructions,
                "turn_detection": turn_detection,
                "audio": {"input": {"format": pcm}, "output": {"format": pcm}},
                "tools": tools or [],
            }
        elif provider == "elevenlabs":
            if model not in {"eleven_realtime_v1_mini", "eleven_realtime_v1_max"}:
                raise ValueError("Unsupported Eleven realtime model")
            if sample_rate != 24000:
                raise ValueError("Eleven Realtime uses PCM at 24000 Hz")
            self.url = "wss://api.elevenlabs.io/v1/convai/realtime"
            self.headers = {}
            self.session = {
                "type": "realtime",
                "model": model,
                "instructions": instructions,
                "output_modalities": ["audio"],
                "audio": {
                    "input": {
                        "format": pcm,
                        "turn_detection": turn_detection,
                        "pacing": pacing,
                    },
                    "output": {
                        "format": {"type": "audio/pcm"},
                        "voice": voice or "brian",
                    },
                },
                "tools": tools or [],
            }
        elif provider == "microsoft_mai":
            if model != "MAI-Transcribe-2-Streaming":
                raise ValueError("Unsupported MAI transcription model")
            if turn_detection is not None or tools:
                raise ValueError("MAI transcription does not support VAD or tools")
            endpoint = urlparse(os.environ["MAI_ENDPOINT"])
            if (
                endpoint.scheme != "https"
                or not (endpoint.hostname or "").endswith(".services.ai.azure.com")
                or endpoint.path not in ("", "/")
            ):
                raise ValueError(
                    "MAI_ENDPOINT must be the HTTPS Foundry resource origin"
                )
            self.url = f"wss://{endpoint.netloc}/mai/v1/realtime?intent=transcription"
            self.headers = {"api-key": os.environ["MAI_API_KEY"]}
            self.session = {
                "type": "transcription",
                "audio": {
                    "input": {
                        "format": pcm,
                        "transcription": {
                            "model": os.environ["MAI_TRANSCRIBE_DEPLOYMENT"],
                            "language": None,
                        },
                        "turn_detection": None,
                        "noise_reduction": None,
                    }
                },
            }
        else:
            raise ValueError("Unsupported realtime provider")

    def __enter__(self):
        if self.provider == "elevenlabs":
            r = requests.post(
                "https://api.elevenlabs.io/v1/convai/realtime/client_secrets",
                headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
                json={"session": self.session, "expires_after": {"seconds": 600}},
                timeout=30,
            )
            r.raise_for_status()
            self.headers = {"Authorization": "Bearer " + r.json()["value"]}
        self.deadline = time.monotonic() + self.timeout
        self.socket = connect(
            self.url,
            additional_headers=self.headers,
            open_timeout=20,
            max_size=16 * 1024 * 1024,
        )
        try:
            if self.provider != "elevenlabs":
                self.send({"type": "session.update", "session": self.session})
                self.wait_for("session.updated")
            else:
                self.wait_for("session.created")
            return self
        except Exception:
            self.socket.close()
            raise

    def __exit__(self, *args):
        if self.socket:
            self.socket.close()
        self.headers.clear()

    def send(self, event):
        if not self.socket:
            raise RuntimeError("Session is not connected")
        if time.monotonic() >= self.deadline:
            raise TimeoutError("Realtime session deadline exceeded")
        self.socket.send(json.dumps(event))

    def receive(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Realtime session deadline exceeded")
        event = json.loads(self.socket.recv(timeout=remaining))
        if event.get("type") == "error":
            raise RuntimeError(
                "Provider rejected a realtime event: "
                + str(event.get("error", {}).get("code", "unknown"))
            )
        return event

    def wait_for(self, event_type):
        while True:
            event = self.receive()
            if event.get("type") == event_type:
                return event

    def append_audio(self, pcm):
        if not pcm or len(pcm) % 2:
            raise ValueError("Audio must be nonempty mono PCM16LE")
        self.send(
            {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(pcm).decode(),
            }
        )

    def commit(self):
        self.send({"type": "input_audio_buffer.commit"})

    def cancel(self):
        self.send({"type": "response.cancel"})

    def submit_tool_result(self, call_id, result):
        self.send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(result),
                },
            }
        )

    def request_response(self):
        self.send({"type": "response.create"})
