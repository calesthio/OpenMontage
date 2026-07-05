# Reference Video Analysis — Transcribe Director

Extract raw speech text from the reference video.

Use `transcriber` when available. Mark the transcript as raw source material that requires human review and rewriting before production. If the video has no audio or transcription is unavailable, output `reference_transcript.status = pending_transcription` with a clear reason.

Do not treat the transcript as automatically publishable copy.
