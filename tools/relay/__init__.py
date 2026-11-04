"""Third-party relay ("中转站") provider support.

Config-driven adapters that route image, video and speech generation through
API relays instead of first-party vendor keys. The package is infrastructure:
the actual BaseTool adapters live in their capability packages
(``tools/graphics/relay_image.py``, ``tools/video/relay_video.py``,
``tools/audio/relay_tts.py``) so the registry and selectors treat them like any
other provider tool.

Layout:
    config.py       load + validate ``relay_providers.yaml`` (never holds secrets)
    protocols.py    request/response contracts (presets + declarative generic)
    engine.py       HTTP execution: submit, poll, resume, download, job files
    mock_server.py  loopback mock relay used by tests and ``python -m tools.relay mock-server``
    __main__.py     CLI: check / list / resume / mock-server
"""
