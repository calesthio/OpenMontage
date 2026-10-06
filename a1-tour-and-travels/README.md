# A1 Tour and Travels — website + growth kit

> ### 🌐 Live site: https://snazim0345.github.io/OpenMontage
> ### 🔗 Short link for print & WhatsApp: **https://tinyurl.com/a1tourstravels**
> ### 📞 Bookings: 7888007234 · 💬 https://wa.me/917888007234
> Marketing playbooks (all free): [`marketing/`](marketing/README.md)

## Hosting status — LIVE ✅

| | |
|---|---|
| **Live site** | **https://snazim0345.github.io/OpenMontage/** — real GitHub Pages hosting, free HTTPS, no warning interstitials |
| **Short link for print/SMS** | **https://tinyurl.com/a1tourstravels** (verified: resolves straight to the site) |
| **Auto-deploy** | `deploy-pages.yml` republishes on every change to this folder |
| **Internal docs** | excluded from the published artifact (only web files go live) |
| **Monitored** | `live-check.yml` weekly; `screenshot.yml` runs a real browser on request |
| **Optional upgrade** | a custom domain (`a1toursandtravel.is-a.dev`, or a paid `.in`/`.com`) → see DOMAIN.md |


---


A complete, mobile-responsive one-page site for a Pune–Mumbai taxi & bus business.
**One file, zero dependencies, no build step:** `index.html` (HTML + CSS + vanilla JS inline).

Open `index.html` directly in any browser, or drop it on any static host
(Netlify / Vercel / GitHub Pages / Hostinger / cPanel) — that's the whole deploy.

## What's in it

| # | Section | Notes |
|---|---------|-------|
| 1 | Sticky header | Car-icon logo, nav (Home / Services / Fleet / Pricing / Contact), green *Call Now*, hamburger drawer on mobile |
| 2 | Hero | Full-bleed photo + dark overlay, `Pune ↔ Mumbai Cabs & Buses`, two CTAs, 3 trust badges |
| 3 | Services | 4 cards — pickup & drop, match cab, bus booking, All India tours |
| 4 | Fleet | Sedan / SUV / Tempo Traveller / AC Bus, each with photo, seat count and *Book Now* |
| 5 | Pricing | Pune ↔ Mumbai fare table (Sedan ₹2500–3000, SUV ₹3500–4500, Tempo ₹6000–8000, Bus ₹500–800/seat) + *prices may vary* note |
| 6 | Why choose us | 24x7, experienced drivers, sanitized vehicles, affordable rates |
| 7 | Booking form | Name, mobile, pickup, drop, date, vehicle, message → opens WhatsApp with everything pre-filled |
| 8 | Testimonials | 3 five-star reviews |
| 8b | FAQ | 6 questions that feed FAQPage rich results |
| 9 | Footer | Contact, quick links, services, service areas (Pune, Mumbai, Lonavala, Nashik, Shirdi, All India), © 2026 |

Plus a floating WhatsApp button, back-to-top button, smooth scroll, scroll-reveal
animations and active-nav highlighting.

## Booking form

The form has **no backend**. On submit it validates the fields and builds a
`https://wa.me/…?text=…` deep link from the values, so the enquiry lands straight
in WhatsApp already written out:

```
*NEW BOOKING ENQUIRY — A1 Tour and Travels*

👤 Name: Rahul Sharma
📱 Mobile: +91 9876543210
📍 Pickup: Hinjewadi, Pune
🏁 Drop: Andheri, Mumbai
📅 Date: Saturday, 11 Oct 2026
🚗 Vehicle: SUV (Ertiga / Innova) — 7 seater
📝 Note: 2 large bags, flight at 6 pm
```

Mobile numbers accept `9876543210`, `+91 98765 43210` or `09876543210`.
If the popup is blocked, the link opens in the same tab and the page shows a
tap-here fallback.

## Changing things

- **Phone / WhatsApp number** — the JavaScript block at the bottom of `index.html`:
  ```js
  var WHATSAPP_NUMBER = '917888007234';  // country code + number, no + or spaces
  var PHONE_NUMBER    = '7888007234';    // local dialling format
  ```
  `PHONE_NUMBER` is applied to every `tel:` link automatically. The visible
  `7888007234` text and the `wa.me` URLs in the markup also use this number —
  find & replace `7888007234` / `917888007234` to change them together.
- **Fares** — edit the four rows in the pricing `<tbody>`.
- **Photos** — the fleet images are Unsplash URLs with `?auto=format&fit=crop&w=800&q=70`.
  Swap them for photos of your own vehicles (put files next to `index.html` and use
  `src="your-car.jpg"`). If an image ever fails to load, JavaScript swaps in a
  branded vector illustration of that vehicle, so the card never looks broken.
- **Colours** — the CSS custom properties at the top of `<style>`
  (`--blue: #0B3D91`, `--orange: #FFA500`, …).

## Notes

- Fonts: Poppins from Google Fonts (`display=swap`); falls back to Inter / system fonts.
- Images are lazy-loaded below the fold; the hero is a CSS background so it paints fast.
- Verified: balanced tags, unique IDs, no dangling anchors, valid JS, in-bounds SVG fallbacks.
- Testimonials are realistic samples — replace with real customer quotes before going live.


---

## SEO built in

- Title, meta description, keywords, canonical, robots, geo tags, hreflang, Open Graph + Twitter cards
- **JSON-LD**: `LocalBusiness` + `TaxiService` (hours, geo, service areas, payment, language) with a
  full `OfferCatalog` carrying the four fares, plus `FAQPage` and `WebSite` schema
- Visible **FAQ section** (`#faq`) whose questions mirror real searches
- `sitemap.xml` and `robots.txt`
- No fabricated data in markup: no fake email, no self-serving `aggregateRating` (Google penalises
  review spam — the visible testimonials are clearly samples to be replaced with real ones)

## Marketing

See [`marketing/README.md`](marketing/README.md) — Google Business Profile setup, directory
listings (with English/Hindi/Marathi copy), WhatsApp Business kit, 20-post social pack,
review engine, referral scheme, vehicle branding and partnership outreach. All zero-cost.

---

## Getting a branded domain (`a1toursandtravel.*`)

See **[DOMAIN.md](DOMAIN.md)** — 5 free options, including the exact Netlify / Cloudflare steps that
give you `https://a1toursandtravel.netlify.app` (or `.pages.dev`) in about 3 minutes, and a
pre-written pull request for a genuinely free `a1toursandtravel.is-a.dev` domain.

Once you've picked a name, one command moves everything:

```bash
bash a1-tour-and-travels/set-url.sh https://a1toursandtravel.netlify.app
```

## Security

Full detail in **[SECURITY.md](SECURITY.md)**. Summary:

- **No server, no database, no login, no plugins** — there is nothing to break into. This is the
  single biggest security advantage this business can have.
- **Content Security Policy** in the page `<head>`: `connect-src 'none'` means nothing on the page
  can transmit data anywhere; only the page's own inline script may run.
- **`_headers`** — real HTTP security headers (HSTS, `X-Frame-Options: DENY`, `Referrer-Policy`,
  `Permissions-Policy`, CSP) for Netlify / Cloudflare Pages, which apply them automatically and free.
  (GitHub Pages does not allow custom headers; the `<meta>` CSP still applies there.)
- All 22 external links use `rel="noopener noreferrer"`; no third-party JavaScript is loaded.
- Form input capped with `maxlength`, strict mobile-number validation, everything
  `encodeURIComponent`-escaped before it touches a URL.
- **SECURITY.md §3** covers the things only you can enable — Google 2-Step Verification, WhatsApp
  two-step PIN, SIM-swap lock, domain ownership. Those, not the website, are the real risks.

## Installable app + offline access

The site is now a **Progressive Web App**: open it on any phone and use
*Add to Home Screen*. It then opens full-screen from an icon like a native app, with two
home-screen shortcuts (**Call**, **Book**) and an **app icon** in the brand colours.

`sw.js` caches the page, so if a customer has no network they still see your phone number and the
WhatsApp link. HTML is deliberately **network-first**, so fares are never stale; only icons and
photos are served from cache.

## Accessibility

- `lang="en-IN"`, proper heading order, landmarks (`header`/`main`/`footer`/`nav`)
- Every form field has a `<label>`; errors are linked with `aria-describedby` and flagged with
  `aria-invalid` so screen readers announce exactly what's wrong
- Error messages and the success notice use `aria-live` regions
- Visible keyboard focus rings; a "skip to content" link; ⌘/Ctrl-safe contrast ratios
- A `<noscript>` banner keeps the phone and WhatsApp reachable if JavaScript is off or blocked
- `prefers-reduced-motion` respected — animations switch off for users who ask for that

## Automatic search submission

`.github/workflows/indexnow.yml` submits the site to **IndexNow** (Bing, Yandex, Seznam,
DuckDuckGo) so changes get re-crawled in minutes rather than weeks — free, no account.
It stays dormant until you set one repository variable:

> Settings → Secrets and variables → Actions → **Variables** → New variable → `SITE_URL`

Set it to your real host once GitHub Pages (or Netlify) is enabled, and every subsequent push
re-submits automatically. **Google** has no such public API — submit your URL once in
**Search Console** (5 minutes, one-time) and it does the rest; steps are in
`marketing/06-seo-partnerships-growth.md §C`.

## Monitoring

`live-check.yml` runs **every Monday** and records to `.diagnostics/live-check.txt`:
HTTP status and content type, the presence of your phone number / FAQ / schema / security meta,
plus the served content types of `manifest.json`, `sw.js`, `sitemap.xml`, every icon and
the `_headers` file, and a reachability check of every Unsplash photo the page uses.
Free uptime + regression monitoring.
