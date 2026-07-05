# Reference Video Analysis — Ingest Director

Resolve the user's Douyin URL or local video path into a local reference video artifact.

Use `video_downloader` first for supported URLs. If the download fails because of login, region, network, platform protection, watermark handling, or unsupported URL structure, stop cleanly and ask for a local file path. Do not bypass platform access controls.

Use `custom_asset_import` for local video files. Preserve the original input, local video path, source type, and any fallback reason in `reference_source`.
