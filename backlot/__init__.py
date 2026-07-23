"""Backlot — the living storyboard.

A read-only, disk-derived production board for OpenMontage. A small local web
server watches ``projects/`` and renders each production's pipeline stages,
script, scene plan, generated assets, decisions, cost, and activity — live.

Design contract (see internal/design/LIVING_STORYBOARD.md):
- Observation, not reporting: all state derives from files the pipeline
  already writes. Agents never update the UI.
- Never block, never break: malformed or missing state degrades gracefully.
- The agent's only duty: ``python -m backlot open <project>`` at pipeline init.
"""

__version__ = "0.1.0"

DEFAULT_PORT = 4750
