# Autopilot: an automated YouTube Shorts and TikTok channel on OpenMontage

Once a day, GitHub Actions starts Claude Code headless. It runs OpenMontage's `animated-explainer`
pipeline end to end (research, proposal, script, scene plan, assets, edit, compose) and hands the
finished 9:16 short to a second job. That job uploads it to YouTube and TikTok.

```
 cron ─► [produce job]  Claude Code + OpenMontage ─► render + publish_request.json
               (AI + generation keys, NO platform keys)          │ artifact
                                                                 ▼
         [publish job]  scripts/autopilot_publish.py ─► youtube_publish / tiktok_publish
               (platform keys, NO AI; re-validates everything)   │
                                                                 ▼
                                 autopilot/history.json committed (no repeat topics)
```

| Piece | File |
|---|---|
| Channel config (your standing approval) | `autopilot/channel.yaml` |
| Evergreen topic list | `autopilot/topics.txt` |
| Agent rules for unattended runs | `skills/meta/autopilot.md` |
| Prompt the agent starts with | `autopilot/run-prompt.md` |
| Upload tools | `tools/publishers/youtube_publish.py`, `tools/publishers/tiktok_publish.py` |
| Upload step | `scripts/autopilot_publish.py` |
| Schedule | `.github/workflows/autopilot-short.yml` |

**Cost per video:** about $0.50–$3 of Claude usage plus about $0–$1 of generation, depending on
providers. Stock footage and Piper TTS are free. The workflow caps Claude spend per run (`AUTOPILOT_MAX_LLM_USD`, default $5).
**Runtime:** about 15–30 minutes per video.

---

## Step 1: Configure the channel (15 min)
Edit `autopilot/channel.yaml`: name, handle, persona, sources, duration, playbook, providers and budget.
Committing this file is your **pre-authorization** for unattended runs. Set
`approval_policy.pre_authorized_full_run: false` to switch it off at any time.

## Step 2: Try it interactively first (30 min)
On your computer, inside this repo:
```bash
make setup                       # Python deps + Remotion
cp .env.example .env             # add ANTHROPIC + at least one TTS + image/stock key
claude                           # then: "Run autopilot for one video, but stop at each gate so I can watch"
```
Watch it on the Backlot board (`python -m backlot open <project>`), then fix anything you don't like in
`channel.yaml` before going unattended.

## Step 3: Connect YouTube (20 min)
1. console.cloud.google.com → new project → enable **YouTube Data API v3**.
2. OAuth consent screen → External → add yourself as a test user, then **Publish app**.
   Apps left in "Testing" get refresh tokens that expire after 7 days.
3. Credentials → OAuth client ID → **Desktop app** → download `client_secret.json` (never commit it).
4. `pip install google-auth-oauthlib && python scripts/get_youtube_token.py client_secret.json`

## Step 4: Connect TikTok (30 min, plus TikTok's review)
1. developers.tiktok.com → create app → add **Login Kit** and **Content Posting API**.
2. Register a redirect URI you own (e.g. `https://your-site.vercel.app/tiktok-callback`).
3. `python scripts/get_tiktok_token.py`
4. Until TikTok audits your app, keep `AUTO_PUBLISH=false`. Videos arrive in your TikTok inbox as drafts.

## Step 5: Add GitHub secrets and variables (10 min)
Settings → Secrets and variables → Actions.
- **Secrets:** `ANTHROPIC_API_KEY`, your generation keys (`ELEVENLABS_API_KEY`, `FAL_KEY`, `PEXELS_API_KEY`, …),
  `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`, `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN`.
- **Variables:** `AUTO_PUBLISH=false`, plus optionally `AUTOPILOT_MODEL` (default `claude-sonnet-5-5`) and `AUTOPILOT_MAX_LLM_USD`.
- **Recommended:** scope the YouTube/TikTok secrets to the `social-publish` **Environment** instead of the repo,
  and add yourself as a **required reviewer**. You then approve each upload with one tap in the GitHub app.

## Step 6: First run
Actions → **Autopilot short** → Run workflow → tick **dry_run**. Download the artifact, watch
`renders/final.mp4`, and read `autopilot-run.jsonl` to see every decision the agent made. Then run it for real.

## Step 7: Review mode, then hands-off
For 2–3 weeks, keep `AUTO_PUBLISH=false`: YouTube uploads stay private and TikTok uploads arrive as drafts.
Check facts against the `source_urls`, then publish. When you trust it, set `AUTO_PUBLISH=true`.

## Step 8: Grow
- Post daily for 90 days. Add a second cron line for twice a day once quality is steady.
- Use YouTube Studio retention: if viewers drop in the first 3 seconds, sharpen `channel.persona` and the hook rules.
- TikTok Creator Rewards pays only for videos over 1 minute. Set `duration_seconds: [65, 80]` for that.
- YouTube demonetizes "mass-produced, repetitive" content. Review mode, a consistent persona and recurring
  series formats are what keep you out of that bucket.

---

## Security model
- **Credential split:** the agent job never sees platform credentials, and the upload job runs no AI.
  A malicious web page that injects instructions into the agent can't reach your channels.
- **Untrusted hand-off:** `autopilot_publish.py` refuses video paths outside `projects/`. It re-checks that the
  video is vertical and 8–180 seconds long with ffprobe, and the publisher tools strip control characters and enforce platform limits.
- **Least privilege:** the YouTube token has `youtube.upload` scope only. Workflow permissions default to
  `contents: read`, and only the publish job gets `contents: write` (to commit `history.json`).
- **Agent allow-list:** Claude Code runs with `--permission-mode dontAsk` and an explicit tool allow-list.
  Note that `Bash(python *)` is still broad, which is why the generation keys in that job should have
  provider-side **spend limits**.
- **Egress monitoring:** `step-security/harden-runner` starts in `audit` mode. After a few runs, copy the
  observed endpoints into `allowed-endpoints` and switch to `block`.
- **No double posts:** the upload tools never auto-retry.
- **Disclosure:** uploads are labeled as AI content (YouTube `containsSyntheticMedia`, TikTok `is_aigc`).
- **Hardening:** pin Actions to commit SHAs, enable secret scanning and push protection, and use a separate
  Google brand account for the channel.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `BLOCKED:` / `blocked.json` in the artifact | A required tool was unavailable or failed. The file names the fix (usually a missing key). |
| YouTube `invalid_grant` | Refresh token expired. Publish the OAuth app (Step 3.2) and re-run the token script. |
| TikTok posts are private | Expected until TikTok audits your app. Use draft mode. |
| Same topic twice | The publish job failed to push `history.json`. Check that job's last step. |
| Run hits the budget cap | Raise `AUTOPILOT_MAX_LLM_USD`, or set `AUTOPILOT_MODEL` to a cheaper model. |
