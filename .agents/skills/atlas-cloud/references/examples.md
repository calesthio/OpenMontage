# Atlas Cloud Examples

All examples expect:

```bash
export ATLASCLOUD_API_KEY="your-api-key"
```

## Text-to-video

```bash
curl -s -X POST "https://api.atlascloud.ai/api/v1/model/generateVideo" \
  -H "Authorization: Bearer $ATLASCLOUD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "bytedance/seedance-2.0-mini/text-to-video",
    "prompt": "A locked-off product shot of a matte black camera rotating on a glass table, soft studio lighting",
    "duration": 5,
    "resolution": "720p",
    "ratio": "16:9",
    "generate_audio": true,
    "watermark": false
  }'
```

## Text-to-image

```bash
curl -s -X POST "https://api.atlascloud.ai/api/v1/model/generateImage" \
  -H "Authorization: Bearer $ATLASCLOUD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/nano-banana-2-lite/text-to-image",
    "prompt": "A clean storyboard frame for a cinematic SaaS product demo, realistic studio lighting",
    "aspect_ratio": "16:9",
    "resolution": "1k",
    "thinking_level": "default"
  }'
```

## Poll a prediction

```bash
curl -s \
  -H "Authorization: Bearer $ATLASCLOUD_API_KEY" \
  "https://api.atlascloud.ai/api/v1/model/prediction/$PREDICTION_ID"
```

## Python polling helper

```python
import os
import time
import requests


API_KEY = os.environ["ATLASCLOUD_API_KEY"]
MEDIA_BASE_URL = "https://api.atlascloud.ai/api/v1"


def poll_prediction(prediction_id: str, interval_seconds: float = 5.0, timeout_seconds: float = 300.0):
    headers = {"Authorization": f"Bearer {API_KEY}"}
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        response = requests.get(
            f"{MEDIA_BASE_URL}/model/prediction/{prediction_id}",
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", payload)
        status = str(data.get("status", "")).lower()

        if status in {"completed", "succeeded"}:
            return data
        if status in {"failed", "canceled", "cancelled", "error"}:
            raise RuntimeError(f"Atlas Cloud generation failed: {data}")

        time.sleep(interval_seconds)

    raise TimeoutError(f"Timed out waiting for Atlas Cloud prediction {prediction_id}")
```

## Upload local media

```python
import os
import requests


API_KEY = os.environ["ATLASCLOUD_API_KEY"]


def upload_media(path: str) -> str:
    with open(path, "rb") as file_obj:
        response = requests.post(
            "https://api.atlascloud.ai/api/v1/model/uploadMedia",
            headers={"Authorization": f"Bearer {API_KEY}"},
            files={"file": file_obj},
            timeout=120,
        )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", payload)
    return data["download_url"]
```

## OpenAI-compatible chat

```python
from openai import OpenAI
import os


client = OpenAI(
    api_key=os.environ["ATLASCLOUD_API_KEY"],
    base_url="https://api.atlascloud.ai/v1",
)

response = client.chat.completions.create(
    model="deepseek-ai/deepseek-v4-pro",
    messages=[
        {"role": "system", "content": "You help plan concise video production steps."},
        {"role": "user", "content": "Draft three shot ideas for a 15-second launch video."},
    ],
    max_tokens=512,
)

print(response.choices[0].message.content)
```
