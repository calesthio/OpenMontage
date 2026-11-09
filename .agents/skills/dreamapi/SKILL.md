---
name: dreamapi
description: Generate images, video, avatars, lip sync, and speech through DreamAPI. Use when the user names DreamAPI or a DreamAPI model id.
---

# DreamAPI

Call `dreamapi_image`, `dreamapi_video`, `dreamapi_avatar`, or `dreamapi_tts` when the user names DreamAPI. Selectors may also route here. Do not swap in Fal, Atlas, or a direct vendor after the user asked for DreamAPI.

Set `DREAMAPI_API_KEY`. The user registers and tops up at https://api.newportai.com/. OpenMontage does not store the key.

1. Read `get_info()["model_catalog"]` and pick an exact model id.
2. Say the tool name, model id, and that DreamAPI bills that key before submitting.
3. Pass local file paths for media inputs. The tool uploads them.
4. Save outputs inside the active `projects/<project>/` tree.
5. To resume, pass the same model and the returned `task_id`. A resume polls that task and does not submit another paid job.

DreamAPI prices depend on the account. Do not invent a dollar cost.
