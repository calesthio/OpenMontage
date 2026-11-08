# Running OpenMontage in Docker

The `Dockerfile` at the repo root builds an image with Python 3.12, FFmpeg, Node.js 22 and the libraries headless Chrome needs for Remotion. It covers the CPU path; local GPU models are not included.

## Build

```bash
docker build -t openmontage .
```

The image is about 2.6 GB. `.dockerignore` leaves out `.env`, so API keys never end up in the image.

## Render a demo

```bash
mkdir -p projects
cp -n .env.example .env   # add your provider keys here if you have them
docker run --rm --env-file .env -v "$PWD/projects:/app/projects" openmontage python render_demo.py world-in-numbers
```

The video is written to `projects/demos/renders/world-in-numbers.mp4`. `python render_demo.py --list` shows the other zero-key demos. The demos render without any keys.

## Check caption staging

Caption burn copies the video into `remotion-composer/public` and writes its props there before Remotion renders. This check runs it as the container user on a 2-second test clip:

```bash
docker run --rm -i openmontage python - <<'EOF'
import subprocess
from tools.video.remotion_caption_burn import RemotionCaptionBurn

subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=2",
                "-f", "lavfi", "-i", "sine=duration=2", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "/app/projects/check.mp4"], check=True)
r = RemotionCaptionBurn().execute({"input_path": "/app/projects/check.mp4",
                                   "output_path": "/app/projects/check-captioned.mp4",
                                   "segments": [{"start": 0.0, "end": 2.0, "text": "hello from docker"}]})
print("success:", r.success, r.error or "")
EOF
```

It prints `success: True` when staging and rendering work.

## Notes

- Create `projects` before the first run. If Docker creates the folder, it belongs to root and the container user cannot write to it.
- The container runs as uid 1000, the usual first user on Linux. If your uid is different, change `-u 1000` in the `Dockerfile`.
- `--env-file .env` passes provider keys at run time.
- Your AI coding assistant still runs on your machine. Point it at the container with `docker exec`, or run the assistant inside the container.
