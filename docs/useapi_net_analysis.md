# useapi.net — Technical Analysis

**Purpose:** Evaluate whether OpenMontage could replicate or benefit from useapi.net's model.  
**Date:** 2026-04-13

---

## What the Service Is

useapi.net is an **account bridge service** — it exposes a unified REST API that drives third-party AI platforms (Midjourney, Google Flow, Kling, Runway, etc.) by operating inside users' own subscription accounts. It is explicitly described as "experimental." You pay $15/month to useapi.net, plus your own subscriptions to each underlying platform.

The key value proposition: official API pricing for services like Midjourney or Google Flow is expensive or nonexistent. useapi.net lets you pay the cheaper web-subscription rate and get API-style access on top.

---

## How It Technically Works

This is not a thin wrapper or a reseller of official APIs. The mechanism is **credential extraction + session hijacking + server-side automation**.

### Midjourney

- Users extract their **Discord user token** from browser DevTools (Network tab → Authorization header on a `/messages` request).
- This token is submitted to useapi.net's `/accounts` endpoint.
- useapi.net's backend impersonates the user's Discord account and sends commands to the Midjourney Bot in Direct Messages.
- The service tracks jobs, manages rate limits, and includes a CAPTCHA solver.
- The account must not be used for anything else while managed by the API — concurrent use breaks job tracking.

**Mechanism: Discord user token theft + server-side Discord client impersonation.**

### Google Flow

- Users extract raw session **cookies** from `https://accounts.google.com/` via browser DevTools (Application tab → Cookies).
- The full cookie blob is submitted to useapi.net's `/accounts` endpoint.
- useapi.net's server now owns the Google session. If the user opens the same account in a browser again, the session breaks and the whole setup must be redone.
- Requires a dedicated throwaway Google account; 2FA must be configured so the session token does not expire.
- After 100 free CAPTCHA credits, users must wire in a third-party CAPTCHA-solving service (AntiCaptcha, CapSolver, etc.).

**Mechanism: stolen Google session cookies held server-side. The server acts as the browser.**

### Other platforms (Kling, Runway, Dreamina, etc.)

Documentation is less detailed, but the pattern is consistent: users hand over session credentials from browser DevTools, and useapi.net's infrastructure replays those sessions against the web UI.

### Supporting infrastructure

- Load balancing across multiple accounts per service (up to 3 per $15 subscription tier).
- Asynchronous job queue with SSE streaming for status updates.
- Built-in CAPTCHA solving (bundled).
- Scheduler for deferred/batched job dispatch.

---

## Supported Services (as of analysis date)

| Category | Platforms |
|---|---|
| Image generation | Midjourney, Google Flow (Imagen 4 / Gemini), Kling, Dreamina, MiniMax |
| Video generation | Kling, Runway, Google Flow, Dreamina, MiniMax, PixVerse |
| Music generation | Mureka, TemPolor |
| Face manipulation | InsightFaceSwap |

13+ services total, with new ones added periodically.

---

## Pricing Model

| Tier | Cost | Accounts per service |
|---|---|---|
| Base | $15/month | 3 accounts |
| +1 sub | $10/month | +3 accounts |

Payment via Stripe or crypto. 14-day full refund if fewer than 50 generations used.

**Effective economics:** users pay ~$10-30/month to underlying platforms (e.g., Midjourney Basic = $10/month) plus $15/month to useapi.net. Total ~$25-45/month for API-level access to multiple generators that would otherwise cost hundreds of dollars at official API rates (where they exist at all).

---

## Could OpenMontage Build Something Similar?

### Technical feasibility: yes, with caveats

OpenMontage already has two tools that use exactly this model:

- `heygen_browser_video` — Playwright-driven HeyGen web UI, session cookies stored in `~/.openmontage/heygen_session.json`
- `google_flow_video` — Google OAuth session captured once, reused for subsequent runs

The core pattern is already in the codebase. Extending it to other platforms means:

1. Playwright script that logs in and extracts session cookies (or Discord user token).
2. A server-side session store that holds those credentials.
3. A job dispatcher that replays web UI actions (form fills, button clicks) against the platform's frontend.
4. A polling loop that detects job completion and extracts the output URL.

**Difficulty varies by platform:**

| Platform | Difficulty | Notes |
|---|---|---|
| Midjourney | Medium | Discord user token approach is well-understood; Discord messages API is stable |
| Google Flow | Medium-Hard | Cookie sessions fragile; Google actively rotates tokens; 2FA complicates reauth |
| Kling / Runway / PixVerse | Medium | Standard web forms; Playwright handles these well |
| Dreamina | Medium | ByteDance property; may apply extra bot detection |

The main engineering work is not the automation itself — it is **session longevity and reauth flows**. Sessions expire. OAuth tokens rotate. Bot detection tightens over time.

### What useapi.net adds that is non-trivial

- Multi-account load balancing to distribute rate limits.
- CAPTCHA solving infrastructure (reCAPTCHA v3 Enterprise is not cheap to solve reliably).
- Maintained compatibility as platform UIs update.
- Customer support for broken setups.

OpenMontage could replicate single-account versions of most of these tools. Multi-account pooling and managed CAPTCHA solving are more significant investments.

---

## Risks

### Terms of Service violations

This is the core risk. Every platform useapi.net wraps prohibits what it does:

- **Discord / Midjourney:** Discord's ToS explicitly bans use of user tokens for automation (`self-bots`). Accounts doing this are subject to permanent ban. Midjourney's ToS separately prohibits unauthorized automation.
- **Google:** Extracting and reusing raw session cookies to drive Google services programmatically violates Google's ToS. The Google Flow platform in particular is consumer-only; Google has no sanctioned API for it.
- **Kling, Runway, others:** Standard SaaS ToS uniformly prohibit scraping, automation, and credential sharing.

useapi.net's own language hedges this: the service is described as "experimental." They put the ToS risk on the user, not themselves.

### Account ban risk

- **Midjourney/Discord bans:** Discord has historically banned self-bot accounts in waves. useapi.net's CAPTCHA solver and rate-limiting reduce detection surface, but do not eliminate it. Recommendation: use dedicated throwaway accounts, not personal accounts.
- **Google session invalidation:** Google's fraud detection can invalidate sessions that are accessed from unusual IPs or patterns. The session-breaks-if-you-log-in-on-browser limitation means every manual access attempt resets the setup.
- **Platform UI changes:** Any significant redesign of the underlying platform's web interface can silently break jobs with no clear error. Maintenance burden is ongoing.

### Reliability

- Dependent on platform uptime AND their own infrastructure.
- No SLA. Experimental service, small team.
- Session expiry causes silent failures unless reauth automation is wired in.
- Rate limits are shared across the account pool; heavy usage degrades all users on the same accounts.

### Legal and compliance

- Sharing user credentials with a third party (useapi.net) means useapi.net's infrastructure holds live session access to your Google account, Discord account, etc. This is a significant supply-chain trust issue for any production pipeline.
- If useapi.net is shut down, acquired, or breached, all connected account credentials are exposed.

---

## Recommendations for OpenMontage

1. **Continue the current approach** (`heygen_browser_video`, `google_flow_video`) for services where you hold your own credentials locally — this is the same technical pattern but with zero third-party credential exposure.

2. **Do not route production credentials through useapi.net.** The credential-sharing model is incompatible with any serious pipeline security posture.

3. **Expand first-party browser tools** to other platforms (Kling, Runway) using Playwright. The existing infrastructure is already proven. This gives the same cost arbitrage as useapi.net for platforms lacking affordable APIs, without credential hand-off.

4. **Use official APIs wherever they exist.** For platforms with real API access (Runway Gen-4 API, Kling API, Replicate-hosted models), prefer that path. It is more reliable, ToS-compliant, and predictable.

5. **Treat browser-automation tools as a cost tier, not a reliability tier.** They are appropriate when subscription credits make per-call cost prohibitive, not as the primary path for guaranteed production output.

---

## Summary

useapi.net is technically a credential-extraction + server-side session replay service. It works today because platform bot detection is imperfect and web UIs are automatable. The model is inherently fragile — sessions expire, UIs change, ToS enforcement tightens. OpenMontage already implements the same pattern for HeyGen and Google Flow. The service is useful as a reference for what is possible, but relying on it as an external vendor introduces unnecessary credential risk and ToS exposure. Building equivalent first-party tools for high-value platforms (Kling, Runway) is the cleaner path.
