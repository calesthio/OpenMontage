"""Shared helpers for the MLX provider family (``mlx_image`` / ``mlx_video`` /
``mlx_caption``).

All three bridge OpenMontage capabilities to the sibling ``mlx-movie-director``
runtime (``python/mlx-movie-director/run.py``) on Apple Silicon. They share the
same environment contract (``MLX_MOVIE_DIRECTOR_DIR`` + venv + run.py), so the
resolution logic lives here once — see ``resolve_mlx_env()``.

Factored out of ``tools/graphics/mlx_image.py`` and ``tools/video/mlx_video.py``
(per a TODO both files carried: "If a third MLX provider appears, factor into
tools/_mlx/env.py"). The third provider is ``mlx_caption``.
"""
