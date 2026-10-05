# A1 Tour and Travels — single-page website

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
