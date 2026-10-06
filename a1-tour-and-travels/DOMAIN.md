# Free domain for A1 Tour and Travels — the exact options

**Goal:** replace the long `raw.githack.com/...` link with something like
`a1toursandtravel.netlify.app` or `a1toursandtravel.is-a.dev`.

## Why I can't just do this for you

Every domain and subdomain on earth — free or paid — is issued to an **account** that must be
verified by an email or phone that belongs to you. There is no service that hands a name to an
automated script with no account, because that's exactly what spammers would abuse.

I checked what my access allows:

| Route | Result |
|---|---|
| Create a repository (needed for a `snazim0345.github.io` style name) | ❌ `403` — my GitHub access is scoped to this one repository |
| Enable GitHub Pages (needed for `snazim0345.github.io/OpenMontage/`) | ❌ `403` — GitHub blocks this for integrations, tested twice |
| Fork + pull-request a free-domain registry (is-a.dev) | ❌ forking creates a repository → same `403` |
| Register with a hosting provider (Netlify / Cloudflare / Vercel) | ❌ needs your email + login |

So this one is a **2–3 minute action by you**, and I've prepared everything so it's just clicking
and pasting. Pick **one** option below — option A is the best value, option C gets you the exact
name you asked for.

---

## Option A — `a1toursandtravel.netlify.app` (recommended) ⏱ 3 min

A **real branded subdomain you choose**, free forever, no credit card. It also unlocks the
security headers (`_headers`) that githack can't apply, free HTTPS, and automatic redeploys.

1. Download the ready-to-deploy zip: **`a1toursandtravel-deploy.zip`** (in the repository root)
   — or just download the files from the `a1-tour-and-travels/` folder.
2. Go to **https://app.netlify.com/drop** and drag the zip/folder onto the page. No signup needed
   to see it deploy.
3. Sign up with Google/GitHub (free) so the site is saved to your account.
4. **Site configuration → Change site name** → type `a1toursandtravel` → Save.
5. Your site is now at **`https://a1toursandtravel.netlify.app`**

Then tell me the name and I'll update the canonical URL, sitemap, robots and schema across the
whole site in one commit.

## Option B — `a1toursandtravel.pages.dev` ⏱ 4 min

Same idea, Cloudflare's version. https://pages.cloudflare.com → *Create application* →
*Pages* → *Upload assets* → drag the same zip → name the project `a1toursandtravel` →
your site is at **`https://a1toursandtravel.pages.dev`**. Cloudflare also honours the
`_headers` file and adds free CDN + DDoS protection.

## Option C — `a1toursandtravel.is-a.dev` (a genuine free domain) ⏱ 2 min

`is-a.dev` is a community project giving free `*.is-a.dev` domains forever, approved through a
GitHub pull request. **The file is already written for you** at
`domains/a1toursandtravel.json` — you just need to submit it from your own GitHub account.

1. Open **https://github.com/is-a-dev/register** and click **Fork** (top-right).
2. In **your fork**, click **Add file → Create new file**.
3. Name it exactly: `domains/a1toursandtravel.json`
4. Paste the contents of `domains/a1toursandtravel.json` from this repository
   (two versions are provided — use the one matching whichever host you set up first).
5. Commit, then click **Contribute → Open pull request**.
6. They review and merge it; your domain goes live within a day or two.

You then set `a1toursandtravel.is-a.dev` as a **custom domain** on the Netlify/Cloudflare site
from Option A/B. Both hosts walk you through the DNS records and issue HTTPS automatically —
free.

> Note: `is-a.dev` requires a working target. Do Option A or B (or GitHub Pages) **first**,
> then point the is-a.dev domain at it.

## Option D — `snazim0345.github.io/OpenMontage/` ⏱ 1 min

Not branded, but clean and permanent, and it activates the automatic deploy workflow.
GitHub → this repo → **Settings → Pages** → Source: *Deploy from a branch* →
branch `arena/54180390-openmontage`, folder `/a1-tour-and-travels` → **Save**.
Live in ~60 seconds. The `deploy-pages.yml` workflow then republishes on every change.

## Option E — a real `a1toursandtravel.eu.org` ⏱ 10 min + wait

EU.org grants **actual free domains** (not subdomains of a hosting brand). Register at
https://nic.eu.org — free, but approval is manual and can take days to weeks. Worth doing
in the background since it's a permanent, genuinely owned domain. Point it at the same host
once approved.

## ❌ Avoid

- `.tk` / `.ml` / `.ga` free domains (Freenom) — the service is effectively dead; links break.
- Any "free domain" site that asks for a card, or that registers the domain **in their name**.
  Whoever holds the registrar account owns your business's name. It must be yours.
- Paid "domain + hosting ₹99" bundles — you don't need hosting; this site is static and free
  to host forever.

---

## Already live right now

A branded **short link** is the one thing I can create without an account, and it's done —
see `.diagnostics/shortlinks.txt` for the verified result. Use it in WhatsApp messages, SMS,
status updates and printed material where a long URL won't fit; it always redirects to the
current site.

## After you pick a name

Run this from the repository root — it updates every canonical reference in one go:

```bash
bash a1-tour-and-travels/set-url.sh https://a1toursandtravel.netlify.app
```

It rewrites the canonical link, Open Graph URLs, schema `@id`/`url`, `sitemap.xml`,
`robots.txt` and the docs, then tells you what changed. Commit and push afterwards, or tell me
and I'll do it along with the Search Console submission.
