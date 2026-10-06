# Security & keeping the website safe

You asked for the site to be protected from attacks. Here's the honest picture, what is
**already done**, and the short list of things only you can switch on.

**Short version: your site is about as attack-proof as a website can be — because it has
almost nothing to attack.**

---

## 1. Why this site is inherently hard to hack

| Attack | Why it can't touch you |
|---|---|
| **Server hacking / ransomware** | There is no server. No PHP, no WordPress, no database, no admin login, no plugins to exploit. Nothing to log into means nothing to break into. |
| **SQL injection** | No database exists. |
| **Login brute-force / credential stuffing** | There are no accounts or passwords anywhere on the site. |
| **Plugin & CMS vulnerabilities** | Zero plugins, zero frameworks. Over 90% of real-world website hacks come in through outdated CMS plugins — you have none. |
| **Form spam / bots** | The booking form doesn't post to a server. It builds a WhatsApp link **in the visitor's own browser** and hands it to WhatsApp. There is nothing to spam. |
| **Data breach / customer data leak** | The site stores **nothing**. No customer records, no payment details, no database. Your booking data lives in your WhatsApp, protected by your phone's lock. |
| **Cross-site scripting (XSS)** | The site is one static file. There is no input that reaches the page as code, no comments, no search box, no user-generated content. |
| **Malware distribution** | You have one HTML file, a stylesheet, two small PNGs and a manifest. Nothing resembling executable content. Virus scanners flag WordPress sites, not this. |

## 2. What I hardened in the code

- **Content Security Policy (CSP)** added in the page `<head>`. This is the big one: it tells the
  browser to only load scripts, styles, fonts and images from a whitelist. Consequences:
  - `script-src` allows only the page's own inline script → an injected external script cannot run
  - `connect-src 'none'` → **nothing on the page can send data anywhere**, so even a successful
    injection has no route to exfiltrate anything
  - `object-src 'none'`, `frame-src 'none'`, `base-uri 'none'`, `form-action 'self'`
  - `upgrade-insecure-requests` → no mixed-content downgrade attacks
- **Every outbound link hardened**: WhatsApp / external links use
  `rel="noopener noreferrer"`, which blocks the classic "tab-nabbing" attack where a linked page
  hijacks your site's tab.
- **No external JavaScript at all** — the only third-party requests are Google Fonts, and photos.
  No analytics scripts, no ad trackers, no CDNs owned by someone else.
- **Input hardening on the booking form**: field length caps (`maxlength`), numeric-only mobile
  input with strict `^[6-9]\d{9}$` validation, and every value passed through
  `encodeURIComponent` before it goes near a URL. Malformed input is rejected in the browser.
- **Content-Type protection**: `X-Content-Type-Options: nosniff` in the headers file, so a browser
  can't be tricked into executing a disguised file.
- **No inline event handlers** (`onclick="..."`) — listeners are attached in JavaScript, which
  keeps the CSP tight and removes a whole class of injection.

## 3. What only you can do (5 minutes, once)

These need your accounts, so no tool can do them for you.

### a) Lock down your Google account (protects your Google Business Profile)
The website is static and safe — but your **Google Business Profile** is a live login, and that
is now the most valuable thing in this business. Anyone who gets into your Google account can
edit your profile, hide your number, or post junk as you.

1. Go to https://myaccount.google.com/security
2. Turn on **2-Step Verification** (use the phone you already have — 7888007234).
3. Add a **recovery email** and **recovery phone**.
4. Review **"Your devices"** and sign out anything you don't recognise.
5. Never share the 6-digit codes with anyone — even someone claiming to be from Google.
   Legitimate Google staff never ask for them.

### b) Use two devices' worth of safety for WhatsApp Business
1. Enable **two-step verification** in WhatsApp → Settings → Account.
2. Set a **fingerprint/PIN screen lock** on the phone that holds the business number.
3. Turn on **chat backup** so a lost phone doesn't lose your booking history.

### c) Freeze out SIM-swap attacks
Your number *is* your business. A "SIM swap" (someone convincing the telecom operator to move
your number to their SIM) would take over both WhatsApp and your OTPs.

1. Call your operator (Jio / Airtel / Vi) and ask for the **SIM-swap lock / port-out lock**.
2. Add a **PIN or verbal password** to your mobile account.
3. Enable the operator's app-based SIM-swap alerts if offered.

### d) Keep these private (never post them)
- OTPs, passwords, and the recovery codes in this repo's `.env.example`
- Your Aadhaar, PAN, driving licence photos and RC — blur them in any photo you post publicly
- Your car's number plate in marketing photos if you don't want it copied — a *signed* vehicle
  sticker is fine (that's how you get calls), just avoid posting documents.

### e) If you ever move to a custom domain
A domain is the only piece of infrastructure you'd own, so protect it:
- Register it in **your own name** (not an agency's), with your own email.
- Turn on **auto-renew** and **domain privacy (WHOIS protection)** — usually free.
- Turn on **two-factor authentication** at the registrar (GoDaddy/Namecheap/Cloudflare).
- Never let a third-party "web company" register your domain for you — they then own your business's name.

## 4. Optional upgrades (free, only if you move hosts)

The file `_headers` in this folder contains **real HTTP security headers**
(HSTS, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, full CSP).

- **GitHub Pages cannot set custom HTTP headers** — that's a hard limitation of theirs.
  The `<meta>` CSP in `index.html` still protects you there.
- **Netlify Drop** (free) and **Cloudflare Pages** (free) honour `_headers` automatically.
  If you ever move the site there, the protection becomes server-enforced on every request —
  plus you get a free real domain like `a1-tour-and-travels.netlify.app`.

Either way, both hosts give **free automatic HTTPS**, so traffic is encrypted end to end.
Never let anyone charge you separately for SSL.

## 5. Monitoring — you'll know if something breaks

A GitHub Actions workflow (`.github/workflows/live-check.yml`) re-checks the live site
**every Monday** and records the result in `.diagnostics/live-history.txt`:

- responds `200` with `content-type: text/html`
- still contains your brand name, phone number, WhatsApp link, FAQ and business schema

If a check ever fails, the history file shows exactly when. That is free uptime monitoring —
no paid service needed.

## 6. If something ever does look wrong

| Symptom | Do this |
|---|---|
| Site shows something you didn't write | Tell me immediately — I can redeploy the exact known-good version from the repository history. |
| Google Business Profile edited/removed | Google → Business Profile → "Request access" / support; check the security page from §3a. |
| WhatsApp sending messages you didn't write | Settings → Linked devices → log out all; change your 2-step PIN; reinstall. |
| Someone calls claiming to be "Google/website support" | Hang up. Google never calls asking for OTPs or payment. This is the #1 scam small businesses face. |
| Suspicious email about your "website renewal" | Ignore unless it's from your actual registrar. "Domain renewal" phishing is extremely common. |

## 7. The honest summary

- **Can this website be hacked?** Realistically, no — there's no server, no login, no database,
  no plugins. A static file has nothing to compromise.
- **The real risks in this business are not the website.** They are your Google account, your
  SIM, your WhatsApp, and social-engineering calls. Section 3 closes all four in about
  5 minutes, and it's the highest-value security work available to you.
- Do not spend money on a "website security" package for this site. Nobody selling you one is
  telling you the truth about what a static site needs.
