# Uploading to YouTube with `youtube_upload`

`tools/publishers/youtube_upload.py` is the networked `publish`-tier tool. It uploads a
finished render to **your own channel** through the YouTube Data API v3, using **your own**
OAuth client. It never publishes immediately:

- by default the video is uploaded as **Private** (only you can see it);
- with `--publish-at` it is uploaded as **Private + scheduled**, and YouTube itself flips it
  to Public at that time;
- `public` is refused in code.

Before a real upload the CLI prints exactly what it will send and waits for you to type
`YES` (or pass `--yes`). In the tool API a real upload requires `confirm=True`.

## 1. Install the Google client libraries (optional dependency)

```bash
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
```

## 2. Create an OAuth client in Google Cloud (about 10 minutes, once)

1. Open https://console.cloud.google.com/ and sign in with **the Google account that owns the channel**.
2. Project picker (top bar) -> **New project** -> any name (e.g. `openmontage-uploader`) -> Create.
3. **APIs & Services -> Library** -> search **YouTube Data API v3** -> **Enable**.
4. **APIs & Services -> OAuth consent screen** (new UI: **Google Auth Platform**):
   - User type **External** -> Create;
   - App name: anything; support and developer e-mail: yours;
   - **Audience / Test users -> Add users** -> add the channel owner's Gmail.
5. **APIs & Services -> Credentials** (or **Clients**) -> **Create credentials -> OAuth client ID**:
   - Application type **Desktop app** -> Create -> **Download JSON**.
6. Rename the file to `client_secret.json` and put it in the config directory:

   ```
   ~/.openmontage/youtube/client_secret.json
   ```

   (Windows: `C:\Users\<you>\.openmontage\youtube\client_secret.json`.) Create the folder if
   needed. Override the directory with the `OPENMONTAGE_YOUTUBE_DIR` environment variable.
   The file lives outside the repository and must never be committed or shared.

## 3. Dry run (no network)

```bash
python -m tools.publishers.youtube_upload --metadata <project>/out/<name>/metadata.json --dry-run
```

Prints the video, thumbnail, title, mode (Private / scheduled) and the full
`videos.insert` request body. Nothing is sent to YouTube.

`metadata.json` carries `title`, `description`, `tags`, `categoryId`, `video` and
`thumbnail`; any of them can be overridden with `--title`, `--video`, `--thumbnail`.

## 4. Upload

Private (open it yourself in YouTube Studio later):

```bash
python -m tools.publishers.youtube_upload --metadata <project>/out/<name>/metadata.json
```

Scheduled (the time is interpreted in your computer's local time zone unless it carries an
offset, and must be at least 15 minutes in the future):

```bash
python -m tools.publishers.youtube_upload --metadata <project>/out/<name>/metadata.json --publish-at "2026-10-20 18:00"
```

On the **first** upload a browser window opens: pick the channel account -> Google warns
"app not verified" -> **Advanced -> Go to ... (unsafe)** -> allow "Manage your YouTube videos".
It is your own app, so this is expected. The token is saved to
`~/.openmontage/youtube/token.json` and the browser will not open again.

From the agent / tool API:

```python
from tools.publishers.youtube_upload import YouTubeUpload

YouTubeUpload().execute({"metadata_path": ".../metadata.json", "dry_run": True})
YouTubeUpload().execute({"metadata_path": ".../metadata.json", "publish_at": "2026-10-20 18:00",
                         "confirm": True})  # only after the user said yes
```

The result's `data["publish_log"]` is a schema-valid `publish_log` entry
(`status: "draft"`, `visibility: "private"` or `"unlisted"`) that can be persisted as the
publish-stage artifact.

## Google's limits, honestly

- **Unverified project means videos locked to Private.** Videos uploaded through the API
  from a project that has not passed YouTube's API audit get a "private viewing only"
  restriction, even with `--publish-at`, and cannot be made public until the project is
  approved. Do a test upload first and check in Studio whether the video carries that label.
  If it does:
  - file the free **YouTube API Services - Audit and Quota Extension** form
    (https://support.google.com/youtube/contact/yt_api_form); once approved, scheduling works;
  - until then upload manually through Studio and use `metadata.json` as the ready-made
    title / description / tags.
- **Token expires after 7 days** while the OAuth consent screen is in *Testing*; the CLI
  simply reopens the browser. To avoid it, press **Publish app** on the consent screen
  (no verification is needed for personal use).
- **Quota:** 10,000 units per day; one upload costs about 1,600 units, so roughly 6 uploads
  per day.
- **Custom thumbnails** are only set if the channel is phone-verified
  (YouTube Studio -> Settings -> Channel -> Feature eligibility). Otherwise the video still
  uploads and the tool reports that the thumbnail was not set.

## Troubleshooting

| message | what to do |
|---|---|
| missing `client_secret.json` | step 2.6: file not there or named differently |
| `access_denied` / `403 ... not a test user` | add your Gmail to Test users (step 2.4) |
| `quotaExceeded` | daily quota exhausted; try again tomorrow |
| `invalid_grant` | delete `token.json` and run again; the sign-in reopens |
