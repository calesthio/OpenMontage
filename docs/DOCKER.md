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

## Notes

- Create `projects` before the first run. If Docker creates the folder, it belongs to root and the container user cannot write to it.
- The container runs as uid 1000, the usual first user on Linux. If your uid is different, change `-u 1000` in the `Dockerfile`.
- `--env-file .env` passes provider keys at run time.
- Your AI coding assistant still runs on your machine. Point it at the container with `docker exec`, or run the assistant inside the container.
