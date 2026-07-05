"""Reference-video v1 downstream target-mode policy."""

SUPPORTED_REFERENCE_TARGET_MODES = ("seedance",)
DEFERRED_REFERENCE_TARGET_MODE_ERROR = (
    "target_mode {target_mode!r} is deferred in reference-video v1; use 'seedance' "
    "for this version."
)
