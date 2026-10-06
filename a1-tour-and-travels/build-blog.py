#!/usr/bin/env python3
"""
Builds the travel-guide articles (blog) for A1 Tour and Travels.

These target *informational* searches — people researching the route before they
book ("pune to mumbai expressway travel time", "cheapest way pune to mumbai").
Informational pages pull in far more visitors than service pages, and each one
funnels readers to the relevant booking page.

Every claim here is deliberately non-numeric where numbers change (current toll
rates, fuel prices) so nothing on the site can become wrong later. Where a
figure is stable — distance, drive time, our own fares — it is stated.

Run:  python3 build-blog.py
"""
import json
import pathlib

SITE = "https://snazim0345.github.io/OpenMontage"
TEL = "tel:+917888007234"
WA_LINK = "https://wa.me/917888007234"
PHONE = "7888007234"

ARTICLES = [
    dict(
        slug="pune-to-mumbai-travel-guide.html",
        title="Pune to Mumbai Travel Guide 2026 | Expressway Time, Best Departure Times & Tips",
        desc="How long the Pune to Mumbai drive really takes, the best times to leave, monsoon and weekend traffic tips, pickup points on both ends, and what to carry. A practical guide.",
        h1="Pune to Mumbai: A Practical Travel Guide",
        sub="Everything worth knowing before you make the Pune–Mumbai run — how long it really takes, when to leave, what changes in the monsoon, and where the traffic actually bites.",
        published="2026-10-06",
        intro=[
            "Pune and Mumbai are roughly 150 km apart, and on a good day the drive takes three to three and a half hours. On a bad day it can take five. The difference is almost never the distance — it is the time you leave, and which side of each city you are starting from.",
            "This guide is written by people who drive this route every single day, for passengers who mostly want one thing: to arrive when they expected to.",
        ],
        sections=[
            ("How long does the Pune to Mumbai drive actually take?",
             ["A realistic breakdown, rather than a best-case number:",
              "Pune city to the Expressway entry — 20 to 45 minutes, depending on whether you are starting in Kothrud, Hinjewadi, Kharadi or Hadapsar. This is the part most estimates leave out.",
              "The Expressway itself — about two hours to the Mumbai end, traffic permitting.",
              "Entering Mumbai and reaching your drop point — 30 minutes to Panvel or Vashi, 60 to 90 minutes to Andheri or Bandra, and longer to South Mumbai or beyond Borivali.",
              "So a door-to-door figure of three and a half hours is a fair expectation for most Pune-to-Mumbai trips, four hours if you are crossing the city at either end, and five on a bad Friday evening."],
             []),
            ("The best times to leave (and the times to avoid)",
             ["Early morning is the single biggest lever you have. A 5 to 6 AM departure from Pune usually reaches Mumbai before the city traffic thickens, and it is a genuinely calm drive.",
              "Good windows: 4–7 AM on any day. Also 10 AM to 2 PM on weekdays, which misses both city rush hours.",
              "Avoid: Friday afternoon and evening leaving Pune, and Sunday evening leaving Mumbai. These are the two peak directions of the week, and both the Expressway and the city roads are at their worst.",
              "Also avoid the Monday morning Pune-bound rush if you are travelling Mumbai to Pune, and the last working day before a long weekend in either direction.",
              "If you have a flight to catch, add at least an extra hour of buffer on a Friday or a Sunday, and consider leaving the night before for a morning departure from Mumbai.",
             ],
             []),
            ("What changes in the monsoon",
             ["The ghat section between Khandala and Lonavala is the part that changes. In heavy rain it slows to a crawl, visibility drops, and water occasionally pools on the inside lane.",
              "Practical consequences: build 45 to 90 minutes of extra time into a monsoon journey, avoid the ghats after dark in a downpour if you have a choice, and expect Lonavala-bound traffic to be far heavier on weekends — the hill station empties Pune and Mumbai into the same stretch of road.",
              "This is one of the genuine reasons to book a cab rather than drive yourself on this route: our drivers do this stretch constantly, in every condition, and know where it floods and where it does not.",
             ],
             []),
            ("Where the traffic actually bites",
             ["Knowing the pinch points helps you plan, even if you are not driving:",
              "Pune end: the Hinjewadi and Wakad approach roads in the morning, and the Katraj–Kondhwa stretch in the evening.",
              "Expressway: the Khandala ghat, and the Khalapur toll plaza on heavy days.",
              "Mumbai end: the Vashi and Kalamboli entry points, the Sion–Dadar corridor, and anything crossing the city north to south.",
              "This is why a fare quoted for Mumbai should always be confirmed against your actual drop point — an Andheri drop and a Colaba drop are not the same journey.",
             ],
             []),
            ("Practical things worth knowing",
             ["Toll, fuel and parking are included in every fare we quote, so there is nothing to pay along the way. If you are driving yourself, the Expressway is a tolled road and rates are revised periodically — check the current rate before you set out.",
              "Fuel stops, food and washroom breaks are easy on this route: there are food courts at the major plazas, and our drivers stop whenever you ask.",
              "Luggage: a sedan comfortably takes two large bags plus cabin bags. If you have more, an SUV is worth the extra.",
              "Charging: every vehicle we run has a charging point, which matters on a route where you will be using maps and messaging.",
              "Payments: cash, UPI, Google Pay and PhonePe all work. There is no card machine, and no advance payment — you pay at the end of the trip.",
             ],
             []),
            ("Bus, match cab or full cab — which suits you",
             ["Bus — cheapest per person, fixed boarding points and departure times.",
              "Match cab (share cab) — a little more than a bus seat, but a car instead of a coach, with far more flexible pickup and timing.",
              "Full cab — your door to your door, your timing and your stops. The best choice for families, groups, anyone with luggage, and anyone whose schedule matters.",
              "If you are unsure, send us your plan and we will tell you which of the three costs least for your exact case — including when the answer is the bus rather than the cab.",
             ],
             ["See fares for the Pune to Mumbai cab", "Compare match cab seat prices", "Check AC bus seat prices"]),
        ],
        faqs=[
            ("How far is Pune from Mumbai?",
             "Roughly 150 km by road via the Mumbai–Pune Expressway."),
            ("How many hours from Pune to Mumbai?",
             "Three to three and a half hours door to door in normal conditions, four hours if you are crossing either city, and longer on Friday evenings and Sunday evenings."),
            ("What is the best time to leave Pune for Mumbai?",
             "Between 4 AM and 7 AM. You avoid Pune's morning rush, reach Mumbai before its traffic builds, and the Expressway is at its calmest."),
            ("Is it safe to drive Pune to Mumbai at night?",
             "The Expressway is well-lit and patrolled, but the ghat section demands care in rain or fog. If you would rather not drive it at night, our drivers run this route around the clock."),
        ],
        related=[("pune-to-mumbai-cab.html", "Pune to Mumbai Cab — fares & booking"),
                 ("match-cab-pune-mumbai.html", "Match Cab — pay per seat"),
                 ("pune-mumbai-bus.html", "Pune to Mumbai AC Bus"),
                 ("pune-to-lonavala-cab.html", "Pune to Lonavala Cab")],
    ),
    dict(
        slug="cheapest-way-pune-to-mumbai.html",
        title="Cheapest Way to Travel Pune to Mumbai | Bus vs Match Cab vs Cab Compared",
        desc="A straight comparison of the cheapest ways to travel between Pune and Mumbai — AC bus seats, match cab (share cab), full cab and train — with real fares and when each one actually saves you money.",
        h1="Cheapest Way to Travel from Pune to Mumbai",
        sub="Four real options, compared honestly by cost and by what you actually get. Including the cases where spending more is the better decision.",
        published="2026-10-06",
        intro=[
            "The cheapest seat between Pune and Mumbai is the AC bus. The cheapest way to travel alone in a car is a match cab. And the cheapest way for a family of four is often a full sedan, because you stop paying per person.",
            "There is no single answer — it depends entirely on how many people are travelling and how much your time and convenience are worth. Here is the arithmetic for each case.",
        ],
        sections=[
            ("The four options at a glance",
             ["AC Bus — from ₹500 to ₹800 per seat. Fixed boarding points, fixed departure times, reserved seat, luggage in the hold. Cheapest per person, least flexible.",
              "Match Cab (share cab) — from ₹500 to ₹900 per seat. A car rather than a coach, more flexible pickup and timing, hourly departures. Slightly more than a bus, noticeably more comfortable.",
              "Full Cab — ₹2500 to ₹3000 for a sedan (4 seats) or ₹3500 to ₹4500 for an SUV (6–7 seats), for the whole vehicle. Toll, fuel, parking and driver included.",
              "Train — there are trains on this corridor, and the fare can be lower than a bus. But you are tied to the timetable, you still need transport to and from the stations at both ends, and tickets on popular timings sell out well in advance."],
             []),
            ("Which one is cheapest for your group size",
             ["This is the calculation that actually matters:",
              "One person travelling alone — the AC bus, or a match cab seat if you want a car. Both are in the same range.",
              "Two people — two bus seats, or two match cab seats. Still cheaper than a full cab, but the gap narrows.",
              "Three people — the arithmetic is close. Three bus seats cost about the same as a shared SUV seat for the group; a full sedan usually wins once you add the cost of getting to and from boarding points.",
              "Four people — a full sedan is now almost always cheaper than four individual seats, and it is door to door. This is the crossover point.",
              "Six or more — an SUV, and for ten or more a Tempo Traveller, which is dramatically cheaper per head than multiple cabs.",
             ],
             ["Pune to Mumbai cab fares", "Match cab seat prices", "Bus seat prices"]),
            ("The cost people forget: getting to the boarding point",
             ["A bus seat at ₹500 looks unbeatable until you price the rest of the journey.",
              "An auto or cab from your home in Hinjewadi or Kharadi to a boarding point can easily cost a few hundred rupees, and then the same again at the other end in Mumbai to reach your final destination.",
              "For a solo traveller that still works out cheaper than a full cab. For two or three people travelling together, the combined cost of those extra hops frequently cancels out the saving on the ticket.",
              "A match cab reduces this problem because pickup is closer to your address, and a full cab removes it entirely — the fare you are quoted is the whole journey, door to door.",
             ],
             []),
            ("When paying more is the right call",
             ["Some trips are worth a full cab even though a bus seat costs less:",
              "You are catching a flight. A bus cannot absorb a two-hour traffic jam, and a missed flight costs far more than the fare difference.",
              "You are carrying more than one bag. Shifting luggage through boarding points is its own kind of expensive.",
              "You are travelling with children or elderly parents. Door to door, with stops when they need them, is worth a great deal.",
              "You are arriving late at night. Reaching a boarding point at midnight and then finding local transport at the far end is not a saving.",
              "You are three or four people. At that point the full cab is usually the cheaper option anyway — not just the nicer one.",
             ],
             []),
            ("How to get the lowest fare without compromising",
             ["Book early for peak dates. Long weekends, Diwali, Christmas and the summer holidays fill up, and the cheapest slots and vehicles go first.",
              "Travel off-peak if you can — an early-morning departure is both faster and easier to place, and it avoids paying for the time that traffic costs you.",
              "Share if you are travelling alone. A match cab seat gets you a car at close to a bus price.",
              "Group up. The single biggest saving available is turning three sedans into one Tempo Traveller.",
              "Ask us which is cheaper. Send your plan to 7888007234 and we will tell you honestly — sometimes the answer is the bus, and we would rather say so than sell you a cab you do not need.",
             ],
             []),
        ],
        faqs=[
            ("What is the cheapest way to travel from Pune to Mumbai?",
             "An AC bus seat, from ₹500 to ₹800. A match cab (share cab) seat starts around the same price and gets you a car instead of a coach."),
            ("Is a cab cheaper than a bus for a family?",
             "For three or four people, usually yes once you add the cost of getting to and from bus boarding points. A sedan (₹2500–₹3000) covers four people door to door."),
            ("Is there a train between Pune and Mumbai?",
             "Yes, the Pune–Mumbai corridor has regular trains and fares can be lower than a bus. You are tied to the timetable, tickets on popular timings sell out, and you still need local transport at both ends."),
            ("How can I reduce the fare for a group?",
             "Use one larger vehicle instead of several small ones. A 17-seater Tempo Traveller is far cheaper per person than three or four sedans — call 7888007234 for a per-head quote."),
        ],
        related=[("pune-mumbai-bus.html", "AC Bus — seat prices"),
                 ("match-cab-pune-mumbai.html", "Match Cab — pay per seat"),
                 ("pune-to-mumbai-cab.html", "Full cab — fixed fare"),
                 ("tempo-traveller-pune.html", "Tempo Traveller for groups")],
    ),
    dict(
        slug="shirdi-darshan-from-pune-one-day.html",
        title="Shirdi Darshan from Pune in One Day | Complete Trip Plan & Timings",
        desc="How to do Shirdi darshan from Pune in a single day — the ideal departure time, how long the drive takes, what to expect at the temple, and how to plan the return. Practical, from drivers who do this route weekly.",
        h1="Shirdi Darshan from Pune in One Day",
        sub="A realistic same-day plan — what time to leave, when to expect the shortest queues, what to carry, and how to fit in Shani Shingnapur without wrecking the schedule.",
        published="2026-10-06",
        intro=[
            "Shirdi is about 185 km from Pune, and a same-day darshan trip is entirely practical — provided you leave early. The people who have a bad day on this route are almost always the ones who left at nine in the morning.",
            "Here is the plan we would give a friend, based on running this trip week after week.",
        ],
        sections=[
            ("The plan, hour by hour",
             ["4:30–5:00 AM — leave Pune. The roads are empty, and you reach Shirdi before the main crowd builds.",
              "8:30–9:00 AM — arrive in Shirdi. Have breakfast, leave your footwear and phones in the vehicle, and join the darshan queue.",
              "9:00–11:00 AM — darshan, and time in the temple complex. Mornings are the calmest part of the day here.",
              "11:00 AM–1:00 PM — prasad, photographs outside the complex, and lunch at one of the many vegetarian places near the temple.",
              "1:00–4:00 PM — either head back, or drive the extra distance to Shani Shingnapur if your group wants to include it.",
              "4:00–7:00 PM — return journey to Pune, arriving in the evening.",
              "If you would rather not start at 4:30 AM, the alternative is an overnight trip with a day's waiting time at Shirdi, so you attend the morning aarti fresh. Both are easy to arrange — just tell us which one you want.",
             ],
             []),
            ("What the drive is like",
             ["The route runs via Ahmednagar on good roads, and the drive is typically four to four and a half hours each way with a tea stop.",
              "It is an easy drive for a driver who knows it, and a tiring one for someone doing it for the first time after a 4:30 AM alarm. This is a route where having a driver genuinely changes the day — you arrive rested and can attend the aarti rather than needing a nap.",
             ],
             []),
            ("Making the queue shorter",
             ["A few things that reliably help:",
              "Arrive early. Before about 10 AM the queue is significantly shorter than in the afternoon.",
              "Book a darshan slot online in advance if your dates are fixed — especially for weekends, Thursdays and festival days, which are the busiest days by a wide margin.",
              "Avoid major festival days unless you specifically want the full crowd experience; on those days the wait can be hours.",
              "Dress simply. There are conventions around the temple that are easier to follow than to work around.",
              "Phones and cameras are not permitted inside — leave them in the vehicle rather than in a queue locker.",
              "Ask your driver where to park. Someone who does this route weekly parks closer and walks less, which matters in the heat.",
             ],
             []),
            ("What to carry",
             ["A light bag with water, a change of clothes if you plan to stay for an aarti, and cash for prasad and offerings — card and UPI work in most shops but not everywhere inside the complex.",
              "Sensible footwear you can slip off easily, and socks if the ground is hot.",
              "A spare set of clothes if you are doing Shani Shingnapur as well — there are conventions around that visit too.",
             ],
             []),
            ("Vehicle choice",
             ["Sedan (4 seater) — couples and small families. The most economical option for this route.",
              "SUV (6–7 seater) — comfortable for a family of five or six, and easier for anyone who finds long drives hard.",
              "Tempo Traveller (12–17 seater) — groups, extended families and pilgrimage parties. Per head, this is the cheapest way for ten or more people to travel, and the whole group stays together.",
              "Tell us how many are travelling and we will suggest the smallest vehicle that fits comfortably — not the largest one available.",
             ],
             ["Pune to Shirdi cab fares", "Tempo Traveller for groups", "All India tour packages"]),
        ],
        faqs=[
            ("Can I do Shirdi darshan from Pune in one day?",
             "Yes. Leaving Pune around 4:30 AM lets you complete darshan and be back the same evening. Most of our Shirdi bookings are single-day round trips."),
            ("What time should I leave Pune for Shirdi?",
             "Between 4:30 and 5:00 AM. You avoid the crowd at the temple and the return drive is not rushed."),
            ("How long is the journey from Pune to Shirdi?",
             "About four to four and a half hours each way, roughly 185 km via Ahmednagar."),
            ("What is the best day to visit Shirdi?",
             "Weekdays are noticeably quieter than weekends. Thursdays and festival days are the busiest — book a darshan slot online if you are travelling on one of those."),
            ("Should I book a cab or drive myself?",
             "Driving is easy but tiring after an early start, and parking near the temple can be difficult. A cab with a driver means you arrive rested and the driver handles parking."),
        ],
        related=[("pune-to-shirdi-cab.html", "Pune to Shirdi Cab — fares & booking"),
                 ("tempo-traveller-pune.html", "Tempo Traveller for groups"),
                 ("tour-packages.html", "All India tour packages"),
                 ("pune-to-mumbai-cab.html", "Pune to Mumbai Cab")],
    ),
]


def page(a):
    title_plain = a["title"].split("|")[0].strip()
    sections = ""
    for heading, paras, links in a["sections"]:
        body = "".join(f"<p>{t}</p>" for t in paras)
        if links:
            body += '<ul class="plain article-links">' + "".join(f"<li>{l}</li>" for l in links) + "</ul>"
        sections += f'      <h2>{heading}</h2>\n      {body}\n'

    faqs_html = "\n".join(
        f'''      <details class="faq">
        <summary>{q}</summary>
        <p>{ans} <a href="{TEL}">Call {PHONE}</a> or <a href="{WA_LINK}" target="_blank" rel="noopener noreferrer">WhatsApp us</a>.</p>
      </details>''' for q, ans in a["faqs"])

    related = "\n".join(f'        <a href="{h}">{l}</a>' for h, l in a["related"])

    article_ld = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": a["h1"], "description": a["desc"],
        "datePublished": a["published"], "dateModified": a["published"],
        "author": {"@type": "Organization", "name": "A1 Tour and Travels"},
        "publisher": {"@type": "Organization", "name": "A1 Tour and Travels",
                      "logo": {"@type": "ImageObject", "url": f"{SITE}/assets/icon-512.png"}},
        "mainEntityOfPage": {"@type": "WebPage", "@id": f"{SITE}/{a['slug']}"},
        "image": f"{SITE}/assets/og-image.png",
        "about": {"@type": "Thing", "name": "Pune Mumbai travel"},
    }
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage",
              "mainEntity": [{"@type": "Question", "name": q,
                              "acceptedAnswer": {"@type": "Answer", "text": ans}} for q, ans in a["faqs"]]}
    crumb_ld = {"@context": "https://schema.org", "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"},
                    {"@type": "ListItem", "position": 2, "name": "Travel guides", "item": f"{SITE}/{a['slug']}"}]}
    lds = "\n".join('<script type="application/ld+json">\n' + json.dumps(d, ensure_ascii=False, indent=1) + '\n</script>'
                    for d in (article_ld, faq_ld, crumb_ld))

    return f'''<!DOCTYPE html>
<html lang="en-IN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<title>{a['title']}</title>
<meta name="description" content="{a['desc']}" />
<meta name="theme-color" content="#0B3D91" />
<meta name="robots" content="index, follow, max-image-preview:large" />
<meta name="geo.region" content="IN-MH" />
<meta name="geo.placename" content="Pune, Maharashtra" />
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self' 'unsafe-inline'; worker-src 'self'; manifest-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'none'; base-uri 'none'; form-action 'self'; frame-src 'none'; object-src 'none'; upgrade-insecure-requests" />
<link rel="canonical" href="{SITE}/{a['slug']}" />
<meta property="og:type" content="article" />
<meta property="og:site_name" content="A1 Tour and Travels" />
<meta property="og:locale" content="en_IN" />
<meta property="og:title" content="{title_plain}" />
<meta property="og:description" content="{a['desc']}" />
<meta property="og:url" content="{SITE}/{a['slug']}" />
<meta property="og:image" content="{SITE}/assets/og-image.png" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta property="article:published_time" content="{a['published']}" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{title_plain}" />
<meta name="twitter:description" content="{a['desc']}" />
<meta name="twitter:image" content="{SITE}/assets/og-image.png" />
<link rel="icon" type="image/png" sizes="32x32" href="assets/favicon-32.png" />
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png" />
<link rel="manifest" href="manifest.json" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
<link rel="stylesheet" href="styles.css" />
{lds}
</head>
<body>
<header class="header">
  <div class="wrap header__inner">
    <a class="logo" href="index.html" aria-label="A1 Tour and Travels home">
      <span class="logo__mark" aria-hidden="true">🚖</span>
      <span class="logo__text">
        <span class="logo__name">A1 Tour and Travels</span>
        <span class="logo__tag">Pune ↔ Mumbai 24x7</span>
      </span>
    </a>
    <nav class="header__nav" aria-label="Main">
      <a href="index.html">Home</a>
      <a href="pune-to-mumbai-cab.html">Pune ⇄ Mumbai</a>
      <a href="match-cab-pune-mumbai.html">Match Cab</a>
      <a href="pune-mumbai-bus.html">Bus</a>
      <a href="tour-packages.html">Tours</a>
    </nav>
    <div class="header__actions">
      <a class="btn btn--call btn--sm" href="{TEL}">📞 {PHONE}</a>
    </div>
  </div>
</header>

<main>
<section class="phero">
  <div class="wrap phero__inner">
    <nav class="crumbs" aria-label="Breadcrumb"><a href="index.html">Home</a> &nbsp;›&nbsp; <span>Travel guides</span></nav>
    <h1>{a['h1']}</h1>
    <p>{a['sub']}</p>
    <div class="phero__cta">
      <a class="btn btn--call" href="{TEL}">📞 Call {PHONE}</a>
      <a class="btn btn--wa" href="{WA_LINK}" target="_blank" rel="noopener noreferrer">💬 WhatsApp for a Quote</a>
    </div>
    <ul class="phero__meta">
      <li>✓ Daily on this route</li>
      <li>✓ Fixed fares, no surge</li>
      <li>✓ 24x7 on call</li>
    </ul>
  </div>
</section>

<section class="section">
  <div class="wrap split">
    <article>
      <p class="lead">{a['intro'][0]}</p>
      <p>{a['intro'][1]}</p>
{sections}
      <h2>Frequently asked questions</h2>
{faqs_html}
    </article>
    <aside>
      <div class="cta" style="padding:24px 20px">
        <h2 style="font-size:1.15rem">Book this trip</h2>
        <p style="font-size:.88rem">Send your dates and group size to <strong>{PHONE}</strong> and we reply with a fixed fare, usually within five minutes.</p>
        <div class="cta__btns" style="display:grid">
          <a class="btn btn--wa" href="{WA_LINK}" target="_blank" rel="noopener noreferrer">💬 WhatsApp {PHONE}</a>
          <a class="btn btn--call" href="{TEL}">📞 Call now</a>
        </div>
      </div>
      <h3 style="margin-top:26px">Fares &amp; booking</h3>
      <div class="related">
{related}
      </div>
    </aside>
  </div>
</section>

<section class="section section--tint">
  <div class="wrap">
    <div class="cta">
      <h2>Travelling soon? Get a fixed fare in two minutes.</h2>
      <p>Call or WhatsApp <strong>{PHONE}</strong> — 24 hours a day, every day.</p>
      <div class="cta__btns">
        <a class="btn btn--call" href="{TEL}">📞 Call {PHONE}</a>
        <a class="btn btn--wa" href="{WA_LINK}" target="_blank" rel="noopener noreferrer">💬 WhatsApp Now</a>
      </div>
    </div>
  </div>
</section>
</main>

<footer class="footer">
  <div class="wrap">
    <div class="footer__cols">
      <div>
        <div class="footer__brand">
          <span class="logo__mark" aria-hidden="true">🚖</span>
          <strong>A1 Tour and Travels</strong>
        </div>
        <p>Pune ↔ Mumbai cabs, match cabs, AC buses and All India tour packages. Fixed fares, verified drivers, 24x7.</p>
        <p><a href="{TEL}"><strong>📞 {PHONE}</strong></a><br />
        <a href="{WA_LINK}" target="_blank" rel="noopener noreferrer">💬 WhatsApp us</a></p>
      </div>
      <div>
        <h4>Travel guides</h4>
        <ul>
          <li><a href="pune-to-mumbai-travel-guide.html">Pune to Mumbai travel guide</a></li>
          <li><a href="cheapest-way-pune-to-mumbai.html">Cheapest way to travel</a></li>
          <li><a href="shirdi-darshan-from-pune-one-day.html">Shirdi darshan in one day</a></li>
        </ul>
      </div>
      <div>
        <h4>Book a ride</h4>
        <ul>
          <li><a href="pune-to-mumbai-cab.html">Pune to Mumbai cab</a></li>
          <li><a href="match-cab-pune-mumbai.html">Match cab (share cab)</a></li>
          <li><a href="pune-mumbai-bus.html">AC bus booking</a></li>
          <li><a href="tour-packages.html">All India tour packages</a></li>
        </ul>
      </div>
    </div>
    <div class="footer__bottom">
      © 2026 A1 Tour and Travels. Pune ↔ Mumbai Cabs &amp; Buses · Match Cabs · All India Tours · {PHONE}
    </div>
  </div>
</footer>

<a class="wa-float" href="{WA_LINK}?text=Hi%20A1%20Tour%20and%20Travels%2C%20I%20have%20a%20booking%20enquiry."
   target="_blank" rel="noopener noreferrer" aria-label="Chat with A1 Tour and Travels on WhatsApp">
  <svg viewBox="0 0 24 24" fill="#fff" aria-hidden="true"><path d="M12.04 2a9.9 9.9 0 0 0-8.4 15.13L2.5 22l5.02-1.3A9.9 9.9 0 1 0 12.04 2zm5.77 14.06c-.24.68-1.4 1.3-1.94 1.35-.54.05-1.03.24-3.47-.72-2.94-1.16-4.79-4.19-4.94-4.38-.14-.19-1.16-1.55-1.16-2.96 0-1.4.73-2.09 1-2.37.24-.29.53-.36.72-.36l.51.01c.17 0 .39-.06.6.46.24.55.8 1.9.87 2.04.07.14.12.31.02.5-.1.19-.15.31-.29.48l-.43.5c-.14.14-.29.3-.12.58.16.29.73 1.2 1.56 1.95 1.07.95 1.9 1.25 2.18 1.39.29.14.46.12.63-.07.16-.19.72-.84.91-1.13.19-.29.39-.24.65-.15.26.1 1.66.79 1.95.93.29.15.48.22.55.34.07.13.07.79-.17 1.47z"/></svg>
</a>
</body>
</html>
'''


def main():
    out = pathlib.Path(__file__).parent
    written = []
    for a in ARTICLES:
        html = page(a)
        (out / a["slug"]).write_text(html, encoding="utf-8")
        written.append((a["slug"], len(html)))

    # rebuild the sitemap: home + service pages + guides
    service = ["pune-to-mumbai-cab.html", "mumbai-to-pune-cab.html", "match-cab-pune-mumbai.html",
               "pune-mumbai-bus.html", "tempo-traveller-pune.html", "pune-to-shirdi-cab.html",
               "pune-to-lonavala-cab.html", "airport-transfer-pune-mumbai.html", "tour-packages.html"]
    guides = [a["slug"] for a in ARTICLES]
    urls = [("", "1.0", "weekly")] + [(u, "0.9", "monthly") for u in service] + [(u, "0.7", "monthly") for u in guides]
    body = "\n".join(
        f'''  <url>
    <loc>{SITE}/{u}</loc>
    <lastmod>2026-10-06</lastmod>
    <changefreq>{f}</changefreq>
    <priority>{pr}</priority>
  </url>''' for u, pr, f in urls)
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!-- Update the domain here and in index.html once a custom domain is live,\n'
        '     or run: bash set-url.sh https://your-new-url  -->\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + body + "\n</urlset>\n", encoding="utf-8")

    print(f"wrote {len(written)} guides:")
    for slug, size in written:
        print(f"  {slug:44} {size/1024:6.1f} KB")
    print(f"  sitemap.xml now lists {len(urls)} URLs")


if __name__ == "__main__":
    main()
