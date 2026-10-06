#!/usr/bin/env python3
"""
Builds the route / service pages for A1 Tour and Travels.

Each page targets one real search query ("pune to mumbai cab", "match cab pune
mumbai", ...), with unique title, meta description, H1, body content, FAQ schema
and breadcrumbs. They share styles.css so there is no framework and no bloat.

Run:  python3 build-pages.py
"""
import json
import pathlib

SITE = "https://snazim0345.github.io/OpenMontage"
PHONE_LOCAL = "7888007234"
WA = "917888007234"

TEL = "tel:+917888007234"
WA_LINK = f"https://wa.me/{WA}"


def wa(text: str) -> str:
    from urllib.parse import quote
    return f"{WA_LINK}?text={quote(text)}"


def money(lo, hi):
    return f"&#8377;{lo:,} &ndash; &#8377;{hi:,}"


# ---------------------------------------------------------------- page content
PAGES = [
    dict(
        slug="pune-to-mumbai-cab.html",
        nav="Pune ⇄ Mumbai Cab",
        title="Pune to Mumbai Cab ₹2500–3000 | Toll, Fuel & Parking Included | A1 Tour and Travels",
        desc="Pune to Mumbai cab at a fixed fare — sedan ₹2500–3000, SUV ₹3500–4500. Doorstep pickup anywhere in Pune, toll and parking included, 24x7. Call 7888007234.",
        h1='Pune to <em>Mumbai Cab</em>',
        sub="Fixed fares, doorstep pickup anywhere in Pune and drop anywhere in Mumbai. Toll, fuel, driver allowance and parking included — no surge, no hidden charges, 24 hours a day.",
        service="Pune to Mumbai Cab Service",
        service_desc="Doorstep Pune to Mumbai cab with sedan, SUV or tempo traveller. Fixed all-inclusive fares, 24x7.",
        price=(2500, 3000),
        facts=[("Distance", "~150 km"), ("Drive time", "3 – 3.5 hours"), ("Sedan", "₹2500 – ₹3000"), ("Available", "24 x 7")],
        sections=[
            ("How much does a Pune to Mumbai cab cost?",
             ["Our fares are fixed and all-inclusive — the price we quote is the price you pay, whether it is 6 in the morning or 2 at night.",
              "Sedan (Dzire / Etios, 4 seater) — &#8377;2500 to &#8377;3000. Best value for 2–4 passengers with luggage.",
              "SUV (Ertiga / Innova, 6–7 seater) — &#8377;3500 to &#8377;4500. Comfortable for families, extra luggage or hill routes.",
              "Tempo Traveller (12–17 seater) — &#8377;6000 to &#8377;8000. For groups, functions and corporate travel.",
              "Toll, fuel, driver allowance and parking are included in every one of those fares. There is no separate toll charge and no night surcharge surprise. The only things that change the price are extra stops, a different pickup or drop point far outside the cities, or a round trip — and we tell you the exact figure before you confirm."],
             [],
            ),
            ("Where do we pick up in Pune?",
             ["Doorstep pickup means your gate, not a bus stand. We regularly pick up from:",
              "Hinjewadi and Wakad (Phase 1, 2 and 3), Baner, Aundh, Balewadi, Pashan",
              "Kharadi, Viman Nagar, Kalyani Nagar, Wagholi, Chandan Nagar",
              "Hadapsar, Magarpatta, Mundhwa, Kondhwa, NIBM, Katraj",
              "Pimpri-Chinchwad, Nigdi, Akurdi, Chinchwad, Bhosari",
              "Shivajinagar, Swargate, Deccan, Kothrud, Karve Nagar, Warje",
              "Pune Airport (PNQ), Pune Railway Station, Swargate and Shivajinagar ST stands",
              "If your address is not on this list, it almost certainly still works — just share a location pin on WhatsApp and we will confirm."],
             [],
            ),
            ("Where do we drop in Mumbai?",
             ["Anywhere inside Mumbai and the wider metropolitan region, including:",
              "Andheri (East and West), Jogeshwari, Goregaon, Malad, Kandivali, Borivali, Dahisar",
              "Bandra, Khar, Santacruz, Vile Parle, Juhu, Powai, Chandivali, Bhandup, Mulund",
              "Dadar, Prabhadevi, Lower Parel, Worli, Colaba, Fort, Churchgate, Marine Lines",
              "Chembur, Ghatkopar, Kurla, Sion, Wadala, Vashi, Nerul, Belapur, Panvel",
              "Thane, Ghodbunder Road, Mira Road, Bhayandar, Vasai, Virar",
              "Mumbai Airport (BOM) Terminal 1 and 2, Dadar, Kurla LTT, CSMT and Borivali railway stations",
              "For Mumbai airport runs we track your flight timing, so a delayed landing does not cost you the cab."],
             [],
            ),
            ("What is included — and what is not",
             ["Included in the fare, always:",
              "Toll charges for the Mumbai–Pune Expressway, fuel, driver allowance and parking at your drop point",
              "Air-conditioned vehicle with a verified, experienced driver",
              "Bottled water and a phone charging point",
              "One luggage set per passenger plus a large bag in the boot",
              "Not included, and only charged if you ask for it:",
              "Extra sightseeing stops on the way (for example Lonavala, Khandala or Karla Caves)",
              "A round trip with waiting time — these are quoted separately and usually work out cheaper per day",
              "Multiple pickup points in Pune or multiple drop points in Mumbai (a small extra, told to you upfront)"],
             [],
            ),
            ("Why people book this route with us",
             ["The Pune–Mumbai run is our home route. We do it every single day, which is exactly why we can keep the price fixed and the timings honest.",
              "Drivers who know the Expressway, the ghats and the city shortcuts — including which Mumbai entry to take depending on your drop point",
              "Emergency pickups and last-minute bookings, including early morning flights and late-night arrivals",
              "Clean, sanitised vehicles with working AC",
              "One number for everything: call or WhatsApp 7888007234 and you are talking to the same team that will send the driver"],
             [],
            ),
        ],
        faqs=[
            ("How much does a Pune to Mumbai cab cost?",
             "A sedan (Dzire/Etios, 4 seater) costs ₹2500–₹3000 one way, an SUV (Ertiga/Innova, 6–7 seater) ₹3500–₹4500, and a 17-seater Tempo Traveller ₹6000–₹8000. Toll, fuel, driver allowance and parking are included."),
            ("How long does the Pune to Mumbai drive take?",
             "Usually 3 to 3.5 hours via the Mumbai–Pune Expressway, depending on traffic, your pickup point in Pune and your drop point in Mumbai. Central Mumbai and Navi Mumbai can add 45–60 minutes in peak hours."),
            ("Do you charge extra for night pickups?",
             "No. Fares are the same at 2 AM as at 2 PM. There is no night surcharge on this route."),
            ("Can I book a one-way cab without paying for the return?",
             "Yes. All fares listed are one-way — you pay only for the journey you take. A round trip is quoted separately and is usually cheaper per day than two one-ways."),
            ("Do you do Pune to Mumbai airport drops?",
             "Yes, and we track your flight timing. Tell us the flight number when booking and we will plan the pickup so you reach the terminal with time to spare."),
            ("How do I book?",
             "Call or WhatsApp 7888007234 with your pickup point, drop point, date and number of passengers. We reply with a fixed fare, usually within five minutes."),
        ],
        related=[("mumbai-to-pune-cab.html", "Mumbai to Pune Cab"),
                 ("match-cab-pune-mumbai.html", "Match Cab — pay per seat"),
                 ("pune-mumbai-bus.html", "AC Bus seat from ₹500"),
                 ("airport-transfer-pune-mumbai.html", "Airport transfers 24x7")],
    ),
    dict(
        slug="mumbai-to-pune-cab.html",
        nav="Mumbai ⇄ Pune Cab",
        title="Mumbai to Pune Cab ₹2500–3000 | Doorstep Pickup 24x7 | A1 Tour and Travels",
        desc="Mumbai to Pune cab with doorstep pickup anywhere in Mumbai, including the airport and railway stations. Sedan ₹2500–3000, SUV ₹3500–4500. Toll included. Call 7888007234.",
        h1='Mumbai to <em>Pune Cab</em>',
        sub="Doorstep pickup anywhere in Mumbai — including BOM airport, Dadar, Kurla LTT and Borivali — and drop at your gate in Pune. Fixed all-inclusive fares, 24 hours a day.",
        service="Mumbai to Pune Cab Service",
        service_desc="Doorstep Mumbai to Pune cab, airport pickups, fixed all-inclusive fares, 24x7.",
        price=(2500, 3000),
        facts=[("Distance", "~150 km"), ("Drive time", "3 – 4 hours"), ("Sedan", "₹2500 – ₹3000"), ("Airport pickup", "Yes, 24x7")],
        sections=[
            ("Fares for the Mumbai to Pune direction",
             ["Same fixed, all-inclusive pricing as the Pune to Mumbai route. Toll, fuel, driver allowance and parking are included in every figure below.",
              "Sedan (Dzire / Etios, 4 seater) — &#8377;2500 to &#8377;3000",
              "SUV (Ertiga / Innova, 6–7 seater) — &#8377;3500 to &#8377;4500",
              "Tempo Traveller (12–17 seater) — &#8377;6000 to &#8377;8000",
              "If your pickup is deep inside South Mumbai (Colaba, Fort, Marine Lines) or far north (Vasai, Virar, Mira Road), tell us when you book — the fare is confirmed as a fixed number before you travel, never adjusted afterwards."],
             [],
            ),
            ("Airport and railway station pickups",
             ["This is the most common reason people call us from the Mumbai side.",
              "Mumbai Airport (BOM) Terminal 1 and Terminal 2 — we track your flight number, so a delayed landing does not cost you the cab",
              "Dadar, Kurla LTT, CSMT, Thane and Borivali railway stations",
              "Hotel, office and home pickups anywhere in the city",
              "Late-night and early-morning arrivals are normal for us. A 3 AM pickup is the same price as a 3 PM one.",
              "If your train or flight is delayed, call us — the driver waits, and we adjust the pickup rather than charging you for a no-show."],
             [],
            ),
            ("Mumbai to Pune via Lonavala",
             ["The Expressway is fast, but plenty of passengers ask for a stop on the way — and it is a genuinely good idea if you have time.",
              "Lonavala and Khandala for the viewpoints, Bhushi Dam and chikki",
              "Karla Caves and Bhaja Caves for a short heritage stop",
              "Tiger Point and Amrutanjan Point on a clear day",
              "Extra stops are quoted as a small addition when you book — never added to the bill afterwards. If you want a full day of sightseeing, ask for a round-trip or a day-hire package instead; it usually costs less than paying by the kilometre."],
             [],
            ),
            ("What to expect on the drive",
             ["From most of Mumbai you reach the Expressway at Vashi, Panvel or Kalamboli. From there it is a straight, fast run to Pune, with the ghat section after Khandala being the only stretch that slows down in heavy rain.",
              "Morning departures before 7 AM are the fastest, especially from the western suburbs",
              "Friday evenings and Sunday evenings are the heaviest — allow an extra hour",
              "During the monsoon, the ghats can slow to a crawl; our drivers do this route daily and adjust the route and timing accordingly",
              "We stop for tea and a washroom break whenever you want — just ask, it is your trip"],
             [],
            ),
        ],
        faqs=[
            ("How much is a cab from Mumbai to Pune?",
             "Sedan ₹2500–₹3000, SUV ₹3500–₹4500 and Tempo Traveller ₹6000–₹8000 for a one-way trip, with toll, fuel, parking and driver allowance included."),
            ("Can you pick me up from Mumbai airport?",
             "Yes. Give us your flight number and terminal when booking and we will track the arrival. The driver waits at the arrivals area with your name."),
            ("Do you charge more for a late-night pickup?",
             "No. There is no night surcharge — the fare is the same 24 hours a day."),
            ("Can we stop at Lonavala on the way?",
             "Yes, extra stops can be added and the additional amount is quoted upfront. If you want several stops, ask for a day-hire package which usually works out cheaper."),
            ("How long does it take to reach Pune from Mumbai?",
             "Three to four hours depending on your pickup point in Mumbai and traffic. South Mumbai and Virar/Vasai add roughly 45–60 minutes."),
        ],
        related=[("pune-to-mumbai-cab.html", "Pune to Mumbai Cab"),
                 ("match-cab-pune-mumbai.html", "Match Cab — pay per seat"),
                 ("airport-transfer-pune-mumbai.html", "Airport transfers 24x7"),
                 ("pune-to-lonavala-cab.html", "Pune to Lonavala Cab")],
    ),
    dict(
        slug="match-cab-pune-mumbai.html",
        nav="Match Cab (Share Cab)",
        title="Match Cab Pune to Mumbai | Pay Per Seat from ₹500 | A1 Tour and Travels",
        desc="Match cab (share cab) between Pune and Mumbai from ₹500 per seat. Departures every hour both ways, AC vehicles, doorstep pickup on the way. Book on 7888007234.",
        h1='Match Cab <em>Pune ⇄ Mumbai</em>',
        sub="Travelling alone or in a pair? Do not pay for the whole cab. A match cab (share cab) lets you pay only for your seat, with departures every hour in both directions.",
        service="Match Cab (Share Cab) Pune Mumbai",
        service_desc="Shared cab between Pune and Mumbai. Pay per seat from ₹500, hourly departures, AC vehicles.",
        price=(500, 900),
        facts=[("Per seat", "₹500 – ₹900"), ("Departures", "Every hour"), ("Vehicle", "AC sedan / SUV"), ("Luggage", "1 bag + 1 cabin")],
        sections=[
            ("How a match cab works",
             ["A match cab is a shared taxi. Instead of paying &#8377;2500–&#8377;3000 for a whole sedan, you pay for one seat — and the other passengers travelling the same way at the same time share the rest.",
              "Tell us your pickup point, drop point and preferred time",
              "We match you with other passengers heading the same direction",
              "We confirm the cab, the exact pickup time and your seat",
              "You travel in an AC vehicle with a verified driver for a fraction of a full cab",
              "Departures run every hour through the day in both directions, and early-morning and late-night slots are available on request."],
             [],
            ),
            ("Per seat fare",
             ["Match cab fares are per person and start lower than any full-cab option:",
              "Standard seat (shared sedan or SUV) — &#8377;500 to &#8377;900 depending on your pickup and drop points",
              "Two seats together (a couple travelling in the same cab) — priced as two seats, still far below a full cab",
              "Full-cab buy-out — if you want the whole vehicle to yourselves, we convert the booking to a normal cab fare",
              "Toll, fuel and driver costs are included in the seat price. There is nothing extra to pay the driver."],
             [],
            ),
            ("Who it suits",
             ["Students travelling between home and college or work",
              "IT professionals doing weekly Pune–Mumbai commutes who do not want to drive",
              "Solo travellers who would rather not pay for an entire cab",
              "Anyone travelling on a fixed schedule who wants a confirmed seat rather than waiting at a bus stand",
              "Small families of two or three, where two or three seats are still cheaper than a full SUV"],
             [],
            ),
            ("Booking a match cab",
             ["Share your travel date, preferred time, pickup point and number of seats on WhatsApp. We confirm your seat and send the driver details ahead of pickup.",
              "Seats fill quickly on Friday evenings, Sunday evenings and around long weekends — booking a day in advance is a good idea.",
              "If your plans change, tell us as early as you can so the seat can go to someone else and your booking can be moved.",
              "For groups of 6 or more, a full SUV or Tempo Traveller usually works out better value than individual seats — ask us and we will tell you honestly which is cheaper."],
             [],
            ),
        ],
        faqs=[
            ("How much is a match cab from Pune to Mumbai?",
             "Seats start at ₹500 per person and go up to about ₹900 depending on your pickup and drop points. Toll, fuel and driver costs are included."),
            ("How often do match cabs leave Pune for Mumbai?",
             "Every hour through the day in both directions, with early-morning and late-night departures on request."),
            ("How many people share the cab?",
             "Usually two to four passengers in a sedan or SUV, so the vehicle stays comfortable. You are never squeezed in beyond the vehicle's seating capacity."),
            ("Can I book two seats for a couple?",
             "Yes. Book two seats and you travel together in the same vehicle."),
            ("Is a match cab safe for a woman travelling alone?",
             "Yes. All our drivers are verified and experienced, vehicle details and driver name are shared with you before pickup, and you can share the trip details with your family. Many of our regular match cab passengers are women travelling alone."),
            ("What if I need to cancel?",
             "Tell us as early as possible on 7888007234 so the seat can be offered to other passengers, and we will move your booking to another departure."),
        ],
        related=[("pune-to-mumbai-cab.html", "Full cab — fixed fare"),
                 ("mumbai-to-pune-cab.html", "Mumbai to Pune Cab"),
                 ("pune-mumbai-bus.html", "AC Bus seat from ₹500"),
                 ("pune-to-lonavala-cab.html", "Pune to Lonavala Cab")],
    ),
    dict(
        slug="pune-mumbai-bus.html",
        nav="AC Bus Booking",
        title="Pune to Mumbai AC Bus | Seat ₹500–800 | Timings & Booking | A1 Tour and Travels",
        desc="Pune to Mumbai AC bus service with reserved seating from ₹500–800 per seat. Daily departures both ways, boarding at convenient points. Book on 7888007234.",
        h1='Pune to Mumbai <em>AC Bus</em>',
        sub="The most economical way to travel the Expressway. Reserved seating, air-conditioned coaches, daily departures in both directions — from ₹500 per seat.",
        service="Pune Mumbai AC Bus Service",
        service_desc="Daily AC bus service between Pune and Mumbai with reserved seating from ₹500 per seat.",
        price=(500, 800),
        facts=[("Per seat", "₹500 – ₹800"), ("Seats", "45 seater AC"), ("Departures", "Daily, both ways"), ("Baggage", "1 large + 1 cabin")],
        sections=[
            ("Bus fares and what you get",
             ["Seat prices on the Pune–Mumbai AC bus run from &#8377;500 to &#8377;800 per person, depending on the departure time and how early you book.",
              "A reserved seat in an air-conditioned coach — no standing, no scramble",
              "Luggage space in the hold for one large bag, plus a cabin bag with you",
              "Departures through the day in both directions, including early morning and late evening",
              "Boarding points on the Pune side and drop points on the Mumbai side that avoid long detours into the city",
              "For a family of four, four bus seats are still cheaper than a full sedan cab — but if you value door-to-door convenience more than the saving, a cab is the better choice and we will tell you so."],
             [],
            ),
            ("How booking works",
             ["We do not use an app or a payment gateway. You message us, we confirm your seats, and you pay on boarding.",
              "Send your travel date, departure preference and number of passengers on WhatsApp",
              "We reply with available departures, the boarding point nearest you and the seat price",
              "We hold your seats and send you the confirmation and boarding details",
              "You pay for the seats at boarding — no advance, no card, no online payment",
              "If you are booking for a group of 10 or more, tell us — group seats can usually be arranged at a better rate, and we can also arrange a full bus if you need one."],
             [],
            ),
            ("Bus versus cab versus match cab",
             ["Choosing between the three comes down to two things: cost and door-to-door convenience.",
              "Bus — cheapest per person (&#8377;500–&#8377;800), fixed boarding points, fixed departure times. Best for solo travellers on a budget and anyone whose schedule matches a departure.",
              "Match cab (share cab) — a little more than a bus seat, but you get doorstep-ish pickup and a car instead of a coach. Best for solo travellers who want more flexibility.",
              "Full cab — the most expensive option but fully flexible: your timing, your door, your stops. Best for families, groups, or anyone with luggage or a tight schedule.",
              "If you are unsure, send us your plan on WhatsApp and we will tell you which of the three costs less for your exact case — even when the answer is the bus."],
             [],
            ),
            ("Things to know before you travel",
             ["Arrive at your boarding point five to ten minutes early — the bus leaves on time",
              "Carry a photo ID for your own convenience; it is not required, but useful if you need to change anything mid-journey",
              "Oversized items such as a bicycle or a large appliance need a special arrangement — ask us before booking",
              "During the monsoon, expect extra time in the ghat section; we build that into departure planning",
              "If you are catching a flight from Mumbai, take the bus with a generous buffer or book a cab instead — a bus cannot absorb a two-hour traffic jam the way a car can"],
             [],
            ),
        ],
        faqs=[
            ("How much is a Pune to Mumbai bus ticket?",
             "₹500 to ₹800 per seat in an AC coach, depending on departure time and how early you book."),
            ("Do the buses have AC and reserved seats?",
             "Yes. Our coaches are air-conditioned 45-seaters with reserved seating — you are not standing."),
            ("How many buses run each day?",
             "There are daily departures in both directions through the day, including early-morning and late-evening services."),
            ("Can I book a full bus for a group or wedding?",
             "Yes. Tell us your date, route and number of passengers on 7888007234 and we will arrange a full coach."),
            ("How do I pay?",
             "You pay at boarding — no advance and no online payment needed. We simply confirm and hold your seats."),
        ],
        related=[("match-cab-pune-mumbai.html", "Match Cab — pay per seat"),
                 ("pune-to-mumbai-cab.html", "Pune to Mumbai Cab"),
                 ("tempo-traveller-pune.html", "Tempo Traveller & bus hire"),
                 ("tour-packages.html", "All India Tour Packages")],
    ),
    dict(
        slug="tempo-traveller-pune.html",
        nav="Tempo Traveller",
        title="Tempo Traveller on Hire in Pune | 12–17 Seater | Groups & Tours | A1 Tour and Travels",
        desc="Tempo Traveller on hire in Pune — 12–17 seater with push-back seats for family functions, weddings, corporate outings and pilgrimage tours. Call 7888007234 for a quote.",
        h1='Tempo Traveller <em>on Hire in Pune</em>',
        sub="12 to 17 seats, push-back chairs, a roof carrier and a driver who has done the route before. The right vehicle when the whole group needs to travel together.",
        service="Tempo Traveller Hire Pune",
        service_desc="12–17 seater Tempo Traveller on hire from Pune for group trips, weddings, corporate outings and tours.",
        price=(6000, 8000),
        facts=[("Seats", "12 – 17"), ("Pune ⇄ Mumbai", "₹6000 – ₹8000"), ("Features", "Push-back seats"), ("Hire", "Per day or per km")],
        sections=[
            ("When a Tempo Traveller makes sense",
             ["A Tempo Traveller is the answer whenever more than seven people are travelling together and you would rather not split into two cars.",
              "Family functions and weddings — guests travelling from Pune to Mumbai, Nashik or Shirdi",
              "Corporate outings, team offsites and client visits where everyone arrives together",
              "Pilgrimage groups to Shirdi, Nashik, Trimbakeshwar, Bhimashankar and Ashtavinayak",
              "School and college trips, picnics and industrial visits",
              "Multi-day tours where luggage — including coolers, food and decorations — has to fit",
              "For a group of 12 people, a Tempo Traveller usually costs less per head than three sedans, and everyone stays together."],
             [],
            ),
            ("What is in the vehicle",
             ["12, 13 or 17 seats depending on the variant, with push-back reclining chairs so a four-hour journey stays comfortable",
              "Air conditioning throughout, working at both ends of the cabin",
              "A roof carrier for extra luggage at no additional charge",
              "Music system, charging points and curtains",
              "A driver and cleaner on long tours, so the group is never waiting around",
              "We tell you the exact seat count and the vehicle's condition before you book — you always know what is turning up."],
             [],
            ),
            ("Hire rates — per day or per kilometre",
             ["Tempo Traveller pricing works two ways, and we will tell you which is cheaper for your trip:",
              "Per-day hire — best for local functions, wedding pickups and city travel where the vehicle stays with you for a fixed number of hours. Includes a minimum kilometre package per day.",
              "Per-kilometre for outstation trips — Pune to Mumbai runs &#8377;6000 to &#8377;8000 one way, depending on the vehicle variant.",
              "Multi-day tours (Shirdi, Nashik, Mahabaleshwar, Goa, Ajanta–Ellora) are quoted as a package that includes driver allowance and vehicle running costs, so you are not doing arithmetic on the road.",
              "Toll, parking and state permits on outstation routes are listed clearly in the quote before you confirm. Nothing is added afterwards."],
             [],
            ),
            ("Booking a Tempo Traveller",
             ["Tell us the date, route, number of passengers and how many days — that is all we need for an accurate quote.",
              "For weddings, book as early as you can: peak season dates in Pune fill up weeks in advance.",
              "If your group number may change, tell us the maximum — it is much easier to give you a bigger vehicle upfront than to find one the day before.",
              "For long tours we share the driver's name and number in advance so your group can coordinate pickup directly.",
              "If it turns out a Tempo Traveller is more than you need, we will say so and suggest an SUV instead — we would rather earn the next booking than oversell this one."],
             [],
            ),
        ],
        faqs=[
            ("What is the hire charge for a Tempo Traveller in Pune?",
             "A Pune to Mumbai one-way trip is ₹6000–₹8000 depending on the variant. Local and multi-day hires are quoted per day with a kilometre package — call 7888007234 with your route for an exact figure."),
            ("How many people can travel in a Tempo Traveller?",
             "12, 13 or 17 passengers depending on the variant, plus the driver and (on long tours) a cleaner."),
            ("Do you provide Tempo Travellers for weddings?",
             "Yes — guest transport, baraat vehicles and multi-point pickups are common bookings. Book early for peak season dates."),
            ("Are push-back seats and AC available?",
             "Yes, both, along with a roof carrier, music system and charging points."),
            ("Do you do multi-day tour hires?",
             "Yes. Shirdi, Nashik, Mahabaleshwar, Goa, Ajanta–Ellora and longer tours are quoted as all-inclusive packages covering driver allowance and vehicle running costs."),
        ],
        related=[("pune-mumbai-bus.html", "AC Bus booking"),
                 ("tour-packages.html", "All India Tour Packages"),
                 ("pune-to-shirdi-cab.html", "Pune to Shirdi Cab"),
                 ("pune-to-mumbai-cab.html", "Pune to Mumbai Cab")],
    ),
    dict(
        slug="pune-to-shirdi-cab.html",
        nav="Pune to Shirdi",
        title="Pune to Shirdi Cab & Tempo Traveller | Darshan Trip | A1 Tour and Travels",
        desc="Pune to Shirdi cab and Tempo Traveller for Sai Baba darshan. Comfortable one-way or round trip, group friendly, verified drivers. Call 7888007234 for a fixed quote.",
        h1='Pune to <em>Shirdi</em> Cab &amp; Tempo Traveller',
        sub="A comfortable drive to Sai Baba darshan — one way or a same-day round trip, by sedan, SUV or Tempo Traveller for the whole group.",
        service="Pune to Shirdi Cab Service",
        service_desc="Cab and Tempo Traveller from Pune to Shirdi for darshan, one-way and round-trip packages.",
        price=(3500, 5000),
        facts=[("Distance", "~185 km"), ("Drive time", "4 – 4.5 hours"), ("Sedan", "₹3500 – ₹5000"), ("Round trip", "Same day possible")],
        sections=[
            ("The journey",
             ["Shirdi is roughly 185 km from Pune, and the drive usually takes four to four and a half hours via Ahmednagar on good roads, with a comfortable tea stop on the way.",
              "An early start — leaving Pune around 4 or 5 AM — gets you to the temple before the main rush and lets you complete darshan and start back the same day.",
              "If you would rather not rush, we can do an overnight trip with a day's waiting time at Shirdi so you attend the morning aarti fresh.",
              "Sedan, SUV or Tempo Traveller — pick whichever suits your group size. For 10 or more, the Tempo Traveller works out cheaper per person than three cabs."],
             [],
            ),
            ("Fares and what they include",
             ["Sedan (4 seater) — approximately &#8377;3500 to &#8377;5000 for a one-way trip, depending on your pickup point in Pune",
              "SUV (6–7 seater) — the comfortable choice for a family, quoted on the same basis",
              "Tempo Traveller (12–17 seater) — best value for groups; ask for a per-head figure",
              "Round trip with waiting time — quoted as a package that includes the driver's halt, so you pay one clear amount",
              "Toll, fuel and driver allowance are included in every quote. The exact figure is confirmed before you travel, based on your pickup point and whether you want a one-way or return journey."],
             [],
            ),
            ("Darshan tips that save you hours",
             ["The temple queues are shortest early in the morning and again after the evening aarti",
              "Book a darshan slot online in advance if your dates are fixed — especially on weekends, Thursdays and festival days, which are the busiest",
              "Dress simply and carry minimal luggage; there is a cloakroom for bags and footwear",
              "Mobile phones and cameras are not allowed inside — leave them in the vehicle",
              "Combine the trip with Shani Shingnapur, which is about 70 km further and fits comfortably if you leave early",
              "Ask your driver to park at a spot he knows — a driver who does this route regularly saves you a long walk in the heat"],
             [],
            ),
            ("Also popular with Shirdi pilgrims",
             ["Nashik and Trimbakeshwar — the Kumbh city and one of the twelve Jyotirlingas, easily combined with Shirdi",
              "Shani Shingnapur — the village famous for houses without doors",
              "Bhimashankar and the Ashtavinayak circuit — multi-day temple tours with a Tempo Traveller",
              "Tell us your plan and we will build the route around the temples you want to cover rather than the other way round."],
             [],
            ),
        ],
        faqs=[
            ("How much is a cab from Pune to Shirdi?",
             "A sedan is approximately ₹3500–₹5000 one way depending on your pickup point; SUVs and Tempo Travellers are quoted according to your group size. Round trips with waiting time are quoted as a package — call 7888007234."),
            ("Can I do Pune to Shirdi and back in one day?",
             "Yes. Leaving Pune around 4–5 AM lets you complete darshan and return the same evening. Many of our Shirdi bookings are single-day round trips."),
            ("How long is the drive?",
             "About four to four and a half hours each way via Ahmednagar, with a tea stop."),
            ("Can we also visit Shani Shingnapur and Nashik?",
             "Yes. Both can be added, and combining them is common. Tell us how many days you have and we will plan the route."),
            ("Do you provide a Tempo Traveller for a group of 15?",
             "Yes, our 17-seater Tempo Traveller is ideal for a group and works out cheaper per person than multiple cars."),
        ],
        related=[("pune-to-lonavala-cab.html", "Pune to Lonavala Cab"),
                 ("tempo-traveller-pune.html", "Tempo Traveller hire"),
                 ("tour-packages.html", "All India Tour Packages"),
                 ("pune-to-mumbai-cab.html", "Pune to Mumbai Cab")],
    ),
    dict(
        slug="pune-to-lonavala-cab.html",
        nav="Pune to Lonavala",
        title="Pune to Lonavala Cab | One Way & Day Trip | ₹1500–2500 | A1 Tour and Travels",
        desc="Pune to Lonavala cab for one-way trips, monsoon drives and sightseeing day trips. Sedan, SUV and Tempo Traveller with verified drivers. Call 7888007234.",
        h1='Pune to <em>Lonavala Cab</em>',
        sub="Less than two hours from Pune — a hill station run that works as a quick one-way drop, a monsoon drive or a full sightseeing day trip with a car and driver.",
        service="Pune to Lonavala Cab",
        service_desc="Cab from Pune to Lonavala for one-way drops, day trips and sightseeing with a driver.",
        price=(1500, 2500),
        facts=[("Distance", "~65 km"), ("Drive time", "1.5 hours"), ("Sedan", "₹1500 – ₹2500"), ("Day trip", "8 hrs / 80 km")],
        sections=[
            ("One-way drop or a day trip",
             ["There are two different Lonavala bookings, and they are priced differently.",
              "One-way drop — a straight transfer from your address in Pune to your hotel, resort or home in Lonavala. Quickest and cheapest option.",
              "Round trip or day trip — the vehicle and driver stay with you for the day, covering the viewpoints, the dam, the caves and lunch, then bring you back. Priced per day with a kilometre package, which works out far better than paying separately for each leg.",
              "Tell us which one you want and we will quote the right one — not the more expensive one."],
             [],
            ),
            ("What to see while you are there",
             ["Bhushi Dam — famous in the monsoon, when the water flows over the steps",
              "Karla Caves and Bhaja Caves — ancient rock-cut Buddhist caves, a short drive from town",
              "Tiger Point, Amrutanjan Point and Lions Point — valley views, best in the early morning",
              "Rajmachi Viewpoint and the Duke's Nose trek base",
              "Lonavala Lake, Tungarli Lake and INS Shivaji's museum area",
              "Lonavala market — chikki, fudge and cheese, the traditional way to end the trip",
              "If you are doing all of this in one day, a day-hire car with a driver is much easier than trying to piece it together with local transport."],
             [],
            ),
            ("Fares",
             ["Sedan (4 seater) — approximately &#8377;1500 to &#8377;2500 for a one-way drop, depending on your pickup point in Pune",
              "SUV (6–7 seater) — for families and extra luggage, quoted on the same basis",
              "Day trip with driver — priced per day with a kilometre package that comfortably covers all the viewpoints, so you are not watching a meter",
              "Tempo Traveller — for groups, priced per day",
              "Toll, fuel and driver allowance are included in the quote. The exact figure depends on your pickup point and how many stops you want, and it is confirmed before you travel."],
             [],
            ),
            ("Monsoon driving in the ghats",
             ["Lonavala is at its most beautiful in the rains — and the ghats are at their most demanding. A few things we do about that:",
              "Our drivers run this route constantly and know which stretches flood and which corners get slippery",
              "We build extra time into monsoon departures rather than promising a time we cannot keep",
              "We will tell you honestly if a particular day's weather makes a viewpoint trip a bad idea",
              "If you are travelling from Mumbai instead, we also cover Mumbai to Lonavala — and a Pune–Lonavala–Mumbai combination trip is a popular way to use a day"],
             [],
            ),
        ],
        faqs=[
            ("How much is a cab from Pune to Lonavala?",
             "A sedan one-way drop is approximately ₹1500–₹2500 depending on your pickup point. Day trips with a driver are quoted per day with a kilometre package."),
            ("Can I book a car for a full day in Lonavala?",
             "Yes. A day-hire car with a driver stays with you for about 8 hours and covers the viewpoints, the caves and the market comfortably."),
            ("How long does the drive take?",
             "About one and a half hours from most of Pune, and slightly longer in heavy monsoon traffic."),
            ("Do you do Pune to Lonavala and then on to Mumbai?",
             "Yes — Pune to Lonavala to Mumbai as a single trip is a common booking and usually cheaper than two separate bookings."),
            ("Can we go for a monsoon day trip?",
             "Absolutely, that is peak season. We build extra travel time into monsoon bookings and our drivers know which points are safe in heavy rain."),
        ],
        related=[("pune-to-mumbai-cab.html", "Pune to Mumbai Cab"),
                 ("pune-to-shirdi-cab.html", "Pune to Shirdi Cab"),
                 ("tempo-traveller-pune.html", "Tempo Traveller hire"),
                 ("match-cab-pune-mumbai.html", "Match Cab — pay per seat")],
    ),
    dict(
        slug="airport-transfer-pune-mumbai.html",
        nav="Airport Transfers",
        title="Pune & Mumbai Airport Transfer | 24x7 with Flight Tracking | A1 Tour and Travels",
        desc="Pune (PNQ) and Mumbai (BOM) airport pickup and drop, 24x7, with flight-timing tracking. Sedan, SUV and Tempo Traveller. Call 7888007234.",
        h1='Pune &amp; Mumbai <em>Airport Transfers</em>',
        sub="Early morning departure or a delayed midnight arrival — someone will be waiting with your name, and the fare does not change with the clock.",
        service="Pune and Mumbai Airport Transfer",
        service_desc="24x7 airport pickup and drop at Pune (PNQ) and Mumbai (BOM) with flight tracking.",
        price=(1200, 3000),
        facts=[("Pune airport (PNQ)", "From ₹900"), ("Mumbai airport (BOM)", "₹2500 – ₹3000"), ("Available", "24 x 7"), ("Flight tracking", "Yes")],
        sections=[
            ("Airport transfers we handle",
             ["Pune Airport (PNQ), Lohegaon — drop-offs and pickups from anywhere in Pune, including Hinjewadi, Kharadi, Baner, Wakad, Hadapsar and Pimpri-Chinchwad",
              "Mumbai Airport (BOM) Terminal 1 and Terminal 2 — direct transfers from Pune, and pickups from anywhere in Mumbai",
              "Transfer between the two airports — fly into Pune and out of Mumbai, or the reverse",
              "Railway station transfers on the same basis: Pune station, Shivajinagar, Dadar, Kurla LTT, CSMT, Borivali, Thane",
              "Hotel and guest house pickups across both cities, including very early departures"],
             [],
            ),
            ("Flight tracking — why it matters",
             ["Give us your flight number when you book and we track it. That means:",
              "If your flight lands late, the driver is still there — you are not paying for a cab that left without you",
              "If your flight lands early, we know to be there sooner",
              "For international arrivals, we allow time for immigration and baggage so the driver waits at the right moment rather than circling",
              "For departures, we plan the pickup time backwards from your flight, accounting for peak-hour traffic on the Expressway if you are coming from the other city",
              "If something changes on the day, one call to 7888007234 and the pickup is adjusted. No cancellation fee for a delayed flight."],
             [],
            ),
            ("Fares",
             ["Pune city to Pune Airport (PNQ) — from &#8377;900 for a sedan, depending on your pickup point",
              "Pune to Mumbai Airport (BOM) — &#8377;2500 to &#8377;3000 for a sedan, &#8377;3500 to &#8377;4500 for an SUV",
              "Mumbai to Pune Airport — quoted the same way, based on your pickup point in Mumbai",
              "Airport to airport transfer — a fixed quoted fare depending on direction and vehicle",
              "Toll, fuel, parking and driver allowance are included. Airport parking charges, if any, are shown in the quote upfront rather than added later.",
              "Late-night and early-morning transfers are charged at the same rate as daytime — there is no night surcharge."],
             [],
            ),
            ("Practical tips for a stress-free flight transfer",
             ["Book at least a few hours ahead, and a day ahead for early-morning departures — 4 AM slots go quickly",
              "For a domestic flight from Mumbai, leaving Pune three to four hours before departure is comfortable; add an extra hour on Friday evenings",
              "Terminal 1 and Terminal 2 at Mumbai are 5 km apart with different access roads — tell us which one your airline uses",
              "Keep your luggage count handy when booking — it decides whether a sedan or an SUV is the right vehicle",
              "If you are carrying oversized baggage or sporting equipment, tell us beforehand so we send the right vehicle"],
             [],
            ),
        ],
        faqs=[
            ("Do you do early-morning airport pickups?",
             "Yes. We run 24x7 and a 4 AM pickup is booked at the same fare as a 4 PM one. There is no night surcharge."),
            ("Will the driver wait if my flight is delayed?",
             "Yes. Share your flight number and we track it, so a delayed landing does not cost you the cab."),
            ("How much is a cab from Pune to Mumbai airport?",
             "₹2500–₹3000 for a sedan and ₹3500–₹4500 for an SUV, with toll, fuel, parking and driver allowance included."),
            ("Can you pick up from Mumbai airport and drop me in Pune?",
             "Yes, that is one of our most common bookings. We track the arrival and the driver waits at the arrivals gate."),
            ("Do you offer transfers between Pune and Mumbai airports?",
             "Yes — airport to airport transfers are a standard booking and are quoted as a fixed fare."),
        ],
        related=[("pune-to-mumbai-cab.html", "Pune to Mumbai Cab"),
                 ("mumbai-to-pune-cab.html", "Mumbai to Pune Cab"),
                 ("match-cab-pune-mumbai.html", "Match Cab — pay per seat"),
                 ("pune-mumbai-bus.html", "AC Bus Booking")],
    ),
    dict(
        slug="tour-packages.html",
        nav="Tour Packages",
        title="All India Tour Packages from Pune | Family, Honeymoon & Pilgrimage | A1 Tour and Travels",
        desc="Customised All India tour packages from Pune — Maharashtra weekend trips, Shirdi and Nashik pilgrimage, Goa, Ajanta–Ellora, Kerala, Rajasthan and more. Call 7888007234.",
        h1='All India <em>Tour Packages</em>',
        sub="Tell us how many days you have and what you want to see. We build the route, arrange the vehicle and driver, and quote one clear price — no packages designed to look cheap and cost more later.",
        service="All India Tour Packages",
        service_desc="Customised tour packages from Pune and Mumbai by cab, SUV and Tempo Traveller across India.",
        price=None,
        facts=[("Weekend trips", "Lonavala, Mahabaleshwar, Alibaug"), ("Pilgrimage", "Shirdi, Nashik, Ashtavinayak"), ("Heritage", "Ajanta–Ellora, Aurangabad"), ("Long tours", "Goa, Kerala, Rajasthan")],
        sections=[
            ("Popular trips from Pune",
             ["We are based on the Pune–Mumbai route, so these are the trips we know best:",
              "Lonavala and Khandala — one day, monsoon viewpoints and the caves",
              "Mahabaleshwar and Panchgani — two days, strawberry farms, viewpoints and Venna Lake",
              "Alibaug and Kashid — two days, coastal roads and the ferry option",
              "Shirdi and Shani Shingnapur — one or two days of darshan",
              "Nashik, Trimbakeshwar and the vineyards — two days",
              "Ajanta and Ellora with Aurangabad — two to three days of world heritage caves",
              "Ashtavinayak circuit — two days covering the eight Ganpati temples",
              "Goa, Kerala, Rajasthan, Char Dham, Vaishno Devi and the Northeast — planned as longer tours with the vehicle and driver travelling with you"],
             [],
            ),
            ("How we build a package",
             ["A package from us is simply a clear, all-in figure for the things you actually need — not a brochure with conditions attached.",
              "Tell us your dates, the number of people, and what you want to see",
              "We suggest a realistic route and the right vehicle for your group size",
              "You get one written quote covering the vehicle, driver allowance, tolls, parking and the number of days",
              "Hotels are booked by you or by us, whichever you prefer — we will tell you the honest difference in cost",
              "No forced shopping stops, no commission restaurants, no rushed itineraries designed to hit a kickback. Our income comes from the vehicle hire, and that is it."],
             [],
            ),
            ("Vehicles for tours",
             ["Sedan (4 seater) — couples and small families on short trips",
              "SUV (6–7 seater) — the most popular choice for family tours with luggage",
              "Tempo Traveller (12–17 seater) — groups, extended families and pilgrimage parties, with a roof carrier for luggage",
              "AC Bus (45 seater) — large groups, school trips, weddings and corporate outings",
              "For multi-day tours the same driver and vehicle stay with you throughout, so you are not re-explaining your itinerary to a new driver every morning."],
             [],
            ),
            ("What to tell us when you enquire",
             ["The more precise you are, the more accurate the quote:",
              "Dates and the number of days and nights",
              "Number of adults, children and senior citizens in the group",
              "Where you want to start and finish — Pune, Mumbai, or a different city",
              "The places you definitely want to cover, and anything you want to skip",
              "Number of large bags, and whether anyone needs extra legroom",
              "Whether you need help arranging hotels",
              "Send all of that on WhatsApp to 7888007234 and we will reply with a route and a price you can compare against anyone else's."],
             [],
            ),
        ],
        faqs=[
            ("Do you arrange hotels as well as the vehicle?",
             "We can book the vehicle and driver on their own, or suggest and arrange accommodation as part of the package — whichever you prefer. We will tell you the cost difference honestly so you can decide."),
            ("Can you build a custom itinerary instead of using a fixed package?",
             "Yes, every tour we run is customised to your dates and interests. There is no fixed departure you have to fit into."),
            ("What is the cheapest way for a group of 15 to travel?",
             "A 17-seater Tempo Traveller with a roof carrier — it works out far cheaper per person than multiple cars and keeps the group together."),
            ("Do you cover destinations outside Maharashtra?",
             "Yes — Goa, Kerala, Rajasthan, Karnataka, Gujarat, the Char Dham route, Vaishno Devi and the Northeast are all arranged with the vehicle and driver travelling with you."),
            ("How far in advance should I book a tour?",
             "A few days is usually enough, but for long weekends, Diwali, Christmas and summer holidays, booking two to three weeks ahead gets you a better vehicle and a better rate."),
        ],
        related=[("pune-to-shirdi-cab.html", "Pune to Shirdi Cab"),
                 ("pune-to-lonavala-cab.html", "Pune to Lonavala Cab"),
                 ("tempo-traveller-pune.html", "Tempo Traveller hire"),
                 ("pune-mumbai-bus.html", "AC Bus Booking")],
    ),
    dict(
        slug="pune-to-nashik-cab.html",
        nav="Pune to Nashik",
        title="Pune to Nashik Cab | Trimbakeshwar, Saptashrungi & Vineyard Trips | 7888007234",
        desc="Pune to Nashik cab with an experienced driver \u2014 one-way drops, Trimbakeshwar darshan, Saptashrungi and vineyard day trips. Tempo Traveller for groups. Call 7888007234.",
        h1='Pune to <em>Nashik Cab</em>',
        sub="One-way drops, temple darshan trips and weekend vineyard runs between Pune and Nashik \u2014 with a driver who knows the ghats and the temple timings.",
        service="Pune to Nashik Cab",
        service_desc="Cab from Pune to Nashik for one-way drops, Trimbakeshwar darshan, Saptashrungi and vineyard day trips.",
        price=(None, None),
        facts=[("Distance", "~210 km"), ("Drive time", "4.5 \u2013 5 hours"), ("Also covers", "Trimbakeshwar, Saptashrungi"), ("Available", "24 x 7")],
        sections=[
            ("Pune to Nashik \u2014 what the trip actually looks like",
             ["Nashik is roughly 210 km from Pune, and there are two ways to go. The direct route runs north through Sangamner and takes about four and a half to five hours. The other way goes via Mumbai on the expressway \u2014 longer, faster roads, and the better choice if you also want to drop someone in Mumbai on the way.",
              "Because it is a half-day drive each way, most bookings fall into one of three shapes:",
              "A straight one-way drop \u2014 Pune address to a Nashik address, or the reverse.",
              "A same-day darshan trip \u2014 leave Pune early, reach Trimbakeshwar or Saptashrungi, and be home the same night. Long, but people do it regularly and our drivers are used to that timetable.",
              "An overnight weekend \u2014 drive up on Saturday, stay the night, come back Sunday. This is the most comfortable option and the one we recommend for families and groups."],
             []),
            ("Trimbakeshwar, Saptashrungi and the temples around Nashik",
             ["Nashik is one of the most important pilgrimage cities in Maharashtra, and most of our Nashik bookings are temple trips rather than business travel.",
              "Trimbakeshwar \u2014 one of the twelve Jyotirlingas, about 28 km from Nashik city, at the source of the Godavari. Mornings are far less crowded than afternoons.",
              "Saptashrungi at Vani \u2014 a Shakti Peeth roughly 60 km from Nashik, up a hill, with a ropeway as well as road access. Tell us in advance if you want the ropeway, because the parking and walking are on different sides.",
              "Panchavati and the Godavari ghats in Nashik city itself \u2014 easy to combine with a city drop.",
              "Shirdi is around two hours from Nashik, so Pune \u2192 Nashik \u2192 Shirdi \u2192 Pune as a single two-day trip is a route we run often and it works out cheaper than two separate bookings.",
              "One practical note: temple timings, queue lengths and parking rules change with the season and with festival crowds. We plan the departure time around the darshan slot you want, not around a fixed schedule."],
             []),
            ("Weekend and vineyard trips",
             ["Nashik is also the wine capital of India, and a large share of our weekend bookings are leisure trips.",
              "Vineyards and tasting rooms in and around the city, plus the restaurants attached to them \u2014 easy to fit into one afternoon.",
              "Sula Fest and harvest-season weekends are the busiest dates of the year; book the vehicle early for those.",
              "Saptashrungi or Trimbakeshwar in the morning and a vineyard in the afternoon is the combination most groups ask for, and it fits comfortably in one day with a car and driver.",
              "We stay with you through the day on these trips, so you are not arranging a fresh cab for every stop \u2014 which on this route is both cheaper and much less hassle."],
             []),
            ("Kumbh Mela and festival crowds",
             ["Nashik and Trimbakeshwar host the Simhastha Kumbh Mela, one of the largest gatherings on earth. On those dates the city runs at capacity, roads are diverted, and hotels and vehicles are booked out months ahead.",
              "If your travel falls near a major festival or a Kumbh period, the practical advice is simple: book the vehicle as early as you can, expect longer driving times inside the city, and be flexible about the exact drop point on the busiest days. We will tell you honestly what is realistic on your dates instead of promising a time we cannot keep.",
              "We also handle full-group travel for events like this \u2014 Tempo Traveller and bus, with multiple pickup points arranged in advance."],
             []),
            ("What the fare depends on",
             ["We quote Nashik trips rather than printing a fixed price, because the honest cost changes a lot with what you actually want:",
              "Whether it is one-way or a round trip with waiting \u2014 round trips work out cheaper per day than two separate one-ways.",
              "Where in Pune and where in Nashik, since the city ends are what usually add distance.",
              "How many stops you want on the way \u2014 Trimbakeshwar, Saptashrungi and a vineyard add real kilometres.",
              "The vehicle: sedan for two to four people, SUV for families with luggage, Tempo Traveller for groups of twelve or more.",
              "Toll, fuel and driver allowance are included in what we quote. Give us your pickup point, drop point, date and number of passengers, and you will have one clear figure \u2014 usually within a few minutes, and it does not change later."],
             []),
        ],
        faqs=[
            ("How far is Nashik from Pune, and how long does the cab take?",
             "About 210 km by the direct Sangamner route, which takes roughly four and a half to five hours depending on traffic and stops."),
            ("How much does a Pune to Nashik cab cost?",
             "It depends on one-way or round trip, the vehicle and your exact pickup and drop points, so we quote it rather than print a number that may not fit your trip. Call or WhatsApp 7888007234 for an exact figure in a few minutes."),
            ("Can we do Trimbakeshwar darshan and return the same day?",
             "Yes. Leave Pune early, do the darshan, and be back the same night \u2014 it is a long day but a common booking. An overnight trip is more comfortable if you have elderly passengers."),
            ("Do you also cover Saptashrungi and Shirdi?",
             "Yes. Saptashrungi at Vani is about 60 km from Nashik and Shirdi is around two hours away, so a two-day Pune \u2192 Nashik \u2192 Saptashrungi \u2192 Shirdi \u2192 Pune route is something we arrange regularly."),
            ("Can we book a Tempo Traveller for a group?",
             "Yes \u2014 12 to 17 seats with push-back seats and a luggage carrier, priced per day with a kilometre package. Send the group size and dates and we will quote the right vehicle."),
        ],
        related=[("pune-to-shirdi-cab.html", "Pune to Shirdi Cab"),
                 ("tempo-traveller-pune.html", "Tempo Traveller hire"),
                 ("tour-packages.html", "Tour packages"),
                 ("pune-to-mumbai-cab.html", "Pune to Mumbai Cab")],
    ),
    dict(
        slug="pune-to-mahabaleshwar-cab.html",
        nav="Pune to Mahabaleshwar",
        title="Pune to Mahabaleshwar Cab | Panchgani & Pratapgad Day Trips | 7888007234",
        desc="Pune to Mahabaleshwar cab for weekend trips, Panchgani and Pratapgad sightseeing. Sedan, SUV and Tempo Traveller with a driver who knows the ghats. Call 7888007234.",
        h1='Pune to <em>Mahabaleshwar Cab</em>',
        sub="Weekend trips and hill-station runs from Pune \u2014 with a driver who has driven the Wai and Panchgani ghats hundreds of times, in every season.",
        service="Pune to Mahabaleshwar Cab",
        service_desc="Cab from Pune to Mahabaleshwar and Panchgani for weekend trips, sightseeing and day tours.",
        price=(None, None),
        facts=[("Distance", "~120 km"), ("Drive time", "3 \u2013 3.5 hours"), ("Also covers", "Panchgani, Pratapgad"), ("Best season", "Oct \u2013 Jun")],
        sections=[
            ("The drive from Pune \u2014 and why the driver matters here",
             ["Mahabaleshwar is about 120 km from Pune, usually reached through Wai and Panchgani. On paper that is a three to three and a half hour drive. In practice, the last stretch is mountain road with hairpin bends, and how comfortable the trip feels depends almost entirely on who is driving.",
              "Our drivers run this route constantly. They know which bends need second gear, where the road surface breaks up after monsoon, and how to drive so that the passengers in the back are not fighting car sickness the whole way.",
              "If this is your first hill drive, sit in the front seat. And if anyone in the group gets travel sick, tell us before the trip \u2014 we will plan a stop at Wai so the last stretch is done fresh rather than tired."],
             []),
            ("What to see, and how to fit it into one trip",
             ["Mahabaleshwar is a plateau, not a single viewpoint. The points sit on different sides of it, and this is exactly where a car with a driver beats trying to use local transport.",
              "Arthur's Seat, Wilson Point (Sunrise Point), Kate's Point and Elphinstone Point \u2014 the main valley views, spread across the plateau.",
              "Venna Lake \u2014 boating, and the food stalls around it.",
              "Panchgani, about 20 km away \u2014 Table Land, Sydney Point and Parsi Point, usually combined into the same day.",
              "Pratapgad fort, about 24 km from Mahabaleshwar \u2014 where Shivaji Maharaj met Afzal Khan. A proper half-day in itself if you want to walk up to the top.",
              "Mapro Garden at Gureghar on the Panchgani road \u2014 the standard stop on the way home for strawberry cream and shopping.",
              "Old Mahabaleshwar temple area, with the Panchganga and Krishna sources \u2014 close to the market and easy to add at the end.",
              "For a two-day trip, the usual split is: viewpoints and the market on day one, then Pratapgad and Panchgani on the way back on day two."],
             []),
            ("Monsoon, winter and the honest advice about each",
             ["October to June is the season most people travel in \u2014 clear valley views, cool evenings, and everything open.",
              "The monsoon is spectacular here \u2014 this is one of the wettest places in Maharashtra \u2014 but it comes with real caveats. Some viewpoints are unreachable or simply pointless in heavy cloud, walking trails get slippery, and the ghats demand slower driving. If you are booking a monsoon trip, we build in extra time rather than promising a schedule we cannot keep, and we will tell you honestly if a particular day looks like a washout.",
              "Winter mornings are genuinely cold by Maharashtra standards, so carry a jacket for sunrise points. Summer is pleasant on the plateau even when Pune is hot.",
              "One thing we will not do is take you to a viewpoint that is unsafe on the day you travel just because it was on your list."],
             []),
            ("What the fare depends on",
             ["We quote Mahabaleshwar trips per booking instead of publishing one figure, because the cost changes with the trip:",
              "One-way drop versus a two-day round trip with the vehicle and driver staying with you \u2014 the round trip is better value per day.",
              "How many viewpoints and detours you want, since Pratapgad and Panchgani add real kilometres.",
              "The vehicle: sedan for two to four, SUV for families and luggage, Tempo Traveller for groups of twelve or more.",
              "Where in Pune you are starting from \u2014 Hinjewadi and Wakad are closer to the expressway, Kondhwa and Hadapsar add time.",
              "Tell us your dates, group size and the places you want to cover, and we will send one clear price that includes toll, fuel and driver allowance \u2014 with no separate hill charge added later."],
             []),
        ],
        faqs=[
            ("How long does it take to drive from Pune to Mahabaleshwar?",
             "About three to three and a half hours for 120 km, via Wai and Panchgani. Monsoon and weekend traffic add to that."),
            ("How much is a cab from Pune to Mahabaleshwar?",
             "It depends on one-way or round trip, the vehicle and how many stops you want, so we quote it per booking. Call or WhatsApp 7888007234 with your dates and you will get one clear figure."),
            ("Can we cover Panchgani and Pratapgad in the same trip?",
             "Yes \u2014 Panchgani is on the way and takes an hour or two, and Pratapgad is about 24 km from Mahabaleshwar. On a two-day trip both fit comfortably."),
            ("Is a day trip from Pune possible?",
             "It can be done, but it is a long day at roughly six to seven hours of driving. For most families a one-night stay is far more enjoyable, and we can quote both so you can compare."),
            ("Do you drive here in the monsoon?",
             "Yes. Our drivers know the ghat roads and we build extra time into monsoon trips. We will also tell you honestly if the weather makes a particular viewpoint unsafe on your date."),
        ],
        related=[("pune-to-lonavala-cab.html", "Pune to Lonavala Cab"),
                 ("pune-to-mumbai-cab.html", "Pune to Mumbai Cab"),
                 ("tempo-traveller-pune.html", "Tempo Traveller hire"),
                 ("tour-packages.html", "Tour packages")],
    ),
    dict(
        slug="pune-to-kolhapur-cab.html",
        nav="Pune to Kolhapur",
        title="Pune to Kolhapur Cab | Mahalaxmi Darshan, Panhala & Jyotiba | 7888007234",
        desc="Pune to Kolhapur cab with experienced drivers \u2014 Mahalaxmi temple darshan, Panhala fort, Jyotiba temple and shopping trips. Sedan, SUV and Tempo Traveller. Call 7888007234.",
        h1='Pune to <em>Kolhapur Cab</em>',
        sub="Darshan trips and family runs to Kolhapur \u2014 straight down the expressway and national highway, with the driver staying with you for Panhala and Jyotiba.",
        service="Pune to Kolhapur Cab",
        service_desc="Cab from Pune to Kolhapur for Mahalaxmi darshan, Panhala fort and Jyotiba temple trips.",
        price=(None, None),
        facts=[("Distance", "~230 km"), ("Drive time", "4.5 \u2013 5 hours"), ("Also covers", "Panhala, Jyotiba"), ("Route", "NH-48 via Satara")],
        sections=[
            ("Pune to Kolhapur \u2014 the straightforward drive",
             ["This is one of the easiest long drives in Maharashtra. The route runs down NH-48 through Katraj, Satara and Karad \u2014 about 230 km, four and a half to five hours with a break. The road is good almost the whole way, which is why so many Kolhapur bookings are single-day temple trips.",
              "We plan one proper stop at Satara or Karad for tea and a washroom, and we leave early for darshan bookings because the queue at the Mahalaxmi temple is at its shortest in the morning."],
             []),
            ("Mahalaxmi, Jyotiba and Panhala \u2014 the three places almost everyone goes",
             ["Ambabai / Mahalaxmi temple in Kolhapur city \u2014 the reason most people make this trip. It sits inside the old city, in a lane complex with no car access, so we drop you at the closest point and tell you exactly where to walk.",
              "Jyotiba temple at Wadi Ratnagiri, about 18 km from the city, up a hill road. The last stretch gets crowded on full-moon days and around Chaitra Purnima, when the whole hill is full of devotees.",
              "Panhala fort, about 20 km from Kolhapur on the way back towards Pune \u2014 a proper hill fort with the Teen Darwaza, and a natural stop on the return leg rather than a separate detour.",
              "We sequence these three so you are not driving back and forth across the city: temple first, then Jyotiba or Panhala depending on your timings, and the rest of the city on the way out. Tell us what matters most to you and we will plan around it."],
             []),
            ("Beyond the temples \u2014 food, shopping and family visits",
             ["Kolhapuri food is a reason to come here on its own \u2014 the tambda and pandhra rassa, and the misal. Ask us and we will take you to a place that is actually good rather than the one with the biggest signboard.",
              "Kolhapuri chappals: the genuine ones are sold in specific shops and lanes, and prices vary enormously. We can drop you at the market area and let you work through it at your own pace.",
              "Rankala Lake and the New Palace area \u2014 easy to add if you have a couple of hours spare.",
              "Family and village visits around Kolhapur, Ichalkaranji or Hatkanangale \u2014 a large share of our bookings are simply people going home, and multiple stops along the way are normal for us. Tell us the addresses and we will plan the order so nobody is waiting."],
             []),
            ("What the fare depends on",
             ["We quote Kolhapur trips per booking rather than printing one number, because the trip shape changes the cost:",
              "One-way drop versus a full-day or two-day trip with the vehicle waiting for you.",
              "Whether you are adding Jyotiba and Panhala, which together add around 40 km plus hill driving.",
              "The vehicle \u2014 sedan, SUV or a Tempo Traveller for a larger family group.",
              "Where in Pune you start from, and whether you need multiple pickup points.",
              "Toll, fuel and driver allowance are included in the quote. Give us your date, group size and the places you want to cover, and we will reply with one figure that does not change on the day."],
             []),
        ],
        faqs=[
            ("How far is Kolhapur from Pune and how long does it take?",
             "About 230 km on NH-48 via Satara, which is roughly four and a half to five hours including one proper break."),
            ("How much does a Pune to Kolhapur cab cost?",
             "It depends on one-way or round trip, the vehicle and whether you add Jyotiba and Panhala, so we quote it per booking. Call or WhatsApp 7888007234 for an exact figure."),
            ("Can we do Mahalaxmi darshan and return to Pune the same day?",
             "Yes, and many people do. Leave Pune early, do the darshan, and be back the same evening. If you also want Jyotiba and Panhala, an overnight stay is far more comfortable."),
            ("Do you go to Jyotiba and Panhala as well?",
             "Yes \u2014 both are included in most of our Kolhapur bookings. Jyotiba is about 18 km from the city and Panhala about 20 km, and we plan them into the same trip rather than as separate hires."),
            ("Can we book a Tempo Traveller for a family group?",
             "Yes \u2014 12 to 17 seats. For larger groups we can arrange more than one vehicle with coordinated pickups, which works well for weddings and family functions."),
        ],
        related=[("tour-packages.html", "Tour packages"),
                 ("tempo-traveller-pune.html", "Tempo Traveller hire"),
                 ("pune-to-shirdi-cab.html", "Pune to Shirdi Cab"),
                 ("pune-to-nashik-cab.html", "Pune to Nashik Cab")],
    ),
]


# ------------------------------------------------------------------- template
def page(p):
    """Render one page as HTML."""
    crumb_items = [("Home", "index.html")] + [(p["nav"], None)]
    crumbs = " &nbsp;›&nbsp; ".join(
        f'<a href="{h}">{t}</a>' if h else f"<span>{t}</span>" for t, h in crumb_items)

    facts = "\n".join(
        f'      <div class="fact"><b>{k}</b><span>{v}</span></div>' for k, v in p["facts"])

    # fare table
    if p["price"]:
        lo, hi = p["price"]
        if p["slug"] == "match-cab-pune-mumbai.html":
            rows = [("Match Cab seat", "Shared AC sedan / SUV", "1 seat", "&#8377;500 &ndash; &#8377;900", "best"),
                    ("Two seats together", "Couple, same vehicle", "2 seats", "&#8377;1000 &ndash; &#8377;1800", ""),
                    ("Full cab buy-out", "Sedan, whole vehicle", "4 seater", "&#8377;2500 &ndash; &#8377;3000", "")]
        elif p["slug"] == "pune-mumbai-bus.html":
            rows = [("AC Bus seat", "45 seater coach", "1 seat", "&#8377;500 &ndash; &#8377;800", "best"),
                    ("Group of 10+", "Better group rate", "10+ seats", "On request", ""),
                    ("Full bus hire", "Weddings, schools, corporate", "45 seats", "On request", "")]
        elif p["slug"] == "airport-transfer-pune-mumbai.html":
            rows = [("Pune city → Pune Airport", "PNQ, Lohegaon", "4 seater", "from &#8377;900", "best"),
                    ("Pune → Mumbai Airport", "BOM, T1 / T2", "4 seater", "&#8377;2500 &ndash; &#8377;3000", ""),
                    ("Pune → Mumbai Airport", "BOM, T1 / T2", "6–7 seater", "&#8377;3500 &ndash; &#8377;4500", ""),
                    ("Airport ↔ Airport", "PNQ to BOM or reverse", "Sedan / SUV", "On request", "")]
        elif lo is None:
            # Routes where the honest answer is a quote, not a printed number.
            rows = [("Sedan", "Dzire / Etios", "4 seater", "On request", "best"),
                    ("SUV", "Ertiga / Innova", "6–7 seater", "On request", ""),
                    ("Tempo Traveller", "Push-back seats", "12–17 seater", "On request", "")]
        else:
            rows = [("Sedan", "Dzire / Etios", "4 seater", money(2500, 3000) if p["slug"].endswith("mumbai-cab.html") else money(lo, hi), "best"),
                    ("SUV", "Ertiga / Innova", "6–7 seater", money(3500, 4500) if p["slug"].endswith("mumbai-cab.html") else "On request", ""),
                    ("Tempo Traveller", "Push-back seats", "12–17 seater", money(6000, 8000) if p["slug"].endswith("mumbai-cab.html") else "On request", "")]
        fare_table = f'''<div class="table-wrap">
  <table>
    <caption class="sr-only">Fares for {p['service']}</caption>
    <thead><tr><th scope="col">Vehicle / option</th><th scope="col">Details</th><th scope="col">Capacity</th><th scope="col">Fare</th></tr></thead>
    <tbody>
''' + "\n".join(
            f'      <tr><td class="td-veh">{a}<small>{b}</small></td><td>{c}</td><td class="td-price{" td-price--best" if d=="best" else ""}">{e}</td></tr>'
            for a, b, c, e, d in rows) + '''
    </tbody>
  </table>
  <div class="note"><span>&#9432;</span><span><b>Prices may vary.</b> Night charges, extra stops and round trips are quoted before you confirm. Call or WhatsApp 7888007234 for an exact figure for your pickup and drop points.</span></div>
</div>'''
    else:
        fare_table = '''<div class="table-wrap">
  <table>
    <caption class="sr-only">Package pricing</caption>
    <thead><tr><th scope="col">Tour length</th><th scope="col">Typical route</th><th scope="col">Vehicle</th><th scope="col">Quote</th></tr></thead>
    <tbody>
      <tr><td class="td-veh">1 day<small>Weekend trip</small></td><td>Lonavala, Alibaug, Shirdi</td><td>Sedan / SUV</td><td class="td-price">On request</td></tr>
      <tr><td class="td-veh">2–3 days<small>Most popular</small></td><td>Mahabaleshwar, Nashik, Ajanta–Ellora</td><td>SUV / Tempo</td><td class="td-price td-price--best">Best value</td></tr>
      <tr><td class="td-veh">4+ days<small>Long tours</small></td><td>Goa, Kerala, Rajasthan, Char Dham</td><td>Tempo / Bus</td><td class="td-price">On request</td></tr>
    </tbody>
  </table>
  <div class="note"><span>&#9432;</span><span><b>Every package is customised.</b> Send your dates, group size and places you want to cover to 7888007234 and we will reply with a route and one clear price.</span></div>
</div>'''

    sections = ""
    for heading, paras, items in p["sections"]:
        body = "".join(f"<p>{t}</p>" for t in paras)
        if items:
            body += '<ul class="plain">' + "".join(f"<li>{i}</li>" for i in items) + "</ul>"
        sections += f'      <h2>{heading}</h2>\n      <div class="rule"></div>\n      {body}\n'

    faqs_html = "\n".join(
        f'''      <details class="faq">
        <summary>{q}</summary>
        <p>{a} <a href="{TEL}">Call {PHONE_LOCAL}</a> or <a href="{WA_LINK}" target="_blank" rel="noopener noreferrer">WhatsApp us</a>.</p>
      </details>''' for q, a in p["faqs"])

    related = "\n".join(
        f'        <a href="{href}">{label}</a>' for href, label in p["related"])

    faq_ld = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": q,
                        "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in p["faqs"]],
    }
    service_ld = {
        "@context": "https://schema.org", "@type": "Service",
        "name": p["service"], "serviceType": p["service"], "description": p["service_desc"],
        "url": f"{SITE}/{p['slug']}",
        "provider": {"@type": "LocalBusiness", "name": "A1 Tour and Travels", "@id": f"{SITE}/#business",
                     "telephone": "+917888007234",
                     "address": {"@type": "PostalAddress", "addressLocality": "Pune",
                                 "addressRegion": "Maharashtra", "addressCountry": "IN"}},
        "areaServed": [{"@type": "City", "name": "Pune"}, {"@type": "City", "name": "Mumbai"},
                       {"@type": "City", "name": "Lonavala"}, {"@type": "City", "name": "Nashik"},
                       {"@type": "City", "name": "Shirdi"}],
        "availableChannel": {"@type": "ServiceChannel", "servicePhone": "+917888007234",
                             "serviceUrl": WA_LINK},
    }
    if p["price"]:
        service_ld["offers"] = {
            "@type": "Offer", "priceCurrency": "INR",
            "priceSpecification": {"@type": "PriceSpecification", "priceCurrency": "INR",
                                   "minPrice": p["price"][0], "maxPrice": p["price"][1]},
            "availability": "https://schema.org/InStock",
        }
    crumb_ld = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": p["nav"], "item": f"{SITE}/{p['slug']}"},
        ],
    }
    lds = "\n".join('<script type="application/ld+json">\n' + json.dumps(d, ensure_ascii=False, indent=1) + '\n</script>'
                    for d in (service_ld, faq_ld, crumb_ld))

    title_plain = p["title"].split("|")[0].strip()
    return f'''<!DOCTYPE html>
<html lang="en-IN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<title>{p['title']}</title>
<meta name="description" content="{p['desc']}" />
<meta name="theme-color" content="#0B3D91" />
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1" />
<meta name="geo.region" content="IN-MH" />
<meta name="geo.placename" content="Pune, Maharashtra" />
<meta name="ICBM" content="18.520430, 73.856743" />
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self' 'unsafe-inline'; worker-src 'self'; manifest-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'none'; base-uri 'none'; form-action 'self'; frame-src 'none'; object-src 'none'; upgrade-insecure-requests" />
<link rel="canonical" href="{SITE}/{p['slug']}" />
<link rel="alternate" hreflang="en-in" href="{SITE}/{p['slug']}" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="A1 Tour and Travels" />
<meta property="og:locale" content="en_IN" />
<meta property="og:title" content="{title_plain}" />
<meta property="og:description" content="{p['desc']}" />
<meta property="og:url" content="{SITE}/{p['slug']}" />
<meta property="og:image" content="{SITE}/assets/og-image.png" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{title_plain}" />
<meta name="twitter:description" content="{p['desc']}" />
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
      <a class="btn btn--call btn--sm" href="{TEL}">📞 {PHONE_LOCAL}</a>
    </div>
  </div>
</header>

<main>
<section class="phero">
  <div class="wrap phero__inner">
    <nav class="crumbs" aria-label="Breadcrumb">{crumbs}</nav>
    <h1>{p['h1']}</h1>
    <p>{p['sub']}</p>
    <div class="phero__cta">
      <a class="btn btn--call" href="{TEL}">📞 Call {PHONE_LOCAL}</a>
      <a class="btn btn--wa" href="{wa('Hi A1 Tour and Travels, I want to enquire about: ' + p['service'])}" target="_blank" rel="noopener noreferrer">💬 WhatsApp for a Quote</a>
    </div>
    <ul class="phero__meta">
      <li>✓ Fixed fares, no surge</li>
      <li>✓ Verified drivers</li>
      <li>✓ Clean, sanitised vehicles</li>
      <li>✓ 24x7 on call</li>
    </ul>
  </div>
</section>

<section class="section">
  <div class="wrap">
    <div class="facts">
{facts}
    </div>
  </div>
</section>

<section class="section section--tint">
  <div class="wrap">
    <h2>Fares</h2>
    <div class="rule"></div>
{fare_table}
  </div>
</section>

<section class="section">
  <div class="wrap split">
    <div>
{sections}
    </div>
    <aside>
      <div class="cta" style="padding:24px 20px">
        <h2 style="font-size:1.15rem">Book in one message</h2>
        <p style="font-size:.88rem">Send your pickup point, drop point, date and number of passengers. You get a fixed fare back, usually in five minutes.</p>
        <div class="cta__btns" style="display:grid">
          <a class="btn btn--wa" href="{WA_LINK}" target="_blank" rel="noopener noreferrer">💬 WhatsApp {PHONE_LOCAL}</a>
          <a class="btn btn--call" href="{TEL}">📞 Call now</a>
        </div>
      </div>
      <h3 style="margin-top:26px">Other services</h3>
      <div class="related">
{related}
      </div>
    </aside>
  </div>
</section>

<section class="section section--tint">
  <div class="wrap">
    <h2>Frequently asked questions</h2>
    <div class="rule"></div>
{faqs_html}
  </div>
</section>

<section class="section">
  <div class="wrap">
    <div class="cta">
      <h2>Ready to travel? Let's get you a fixed fare.</h2>
      <p>Call or WhatsApp <strong>{PHONE_LOCAL}</strong> — 24 hours a day, every day. Tell us your route and we will confirm the price before you commit.</p>
      <div class="cta__btns">
        <a class="btn btn--call" href="{TEL}">📞 Call {PHONE_LOCAL}</a>
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
        <p><a href="{TEL}"><strong>📞 {PHONE_LOCAL}</strong></a><br />
        <a href="{WA_LINK}" target="_blank" rel="noopener noreferrer">💬 WhatsApp us</a></p>
      </div>
      <div>
        <h4>Popular routes</h4>
        <ul>
          <li><a href="pune-to-mumbai-cab.html">Pune to Mumbai cab</a></li>
          <li><a href="mumbai-to-pune-cab.html">Mumbai to Pune cab</a></li>
          <li><a href="match-cab-pune-mumbai.html">Match cab (share cab)</a></li>
          <li><a href="pune-mumbai-bus.html">Pune to Mumbai bus</a></li>
          <li><a href="pune-to-lonavala-cab.html">Pune to Lonavala cab</a></li>
          <li><a href="pune-to-shirdi-cab.html">Pune to Shirdi cab</a></li>
        </ul>
      </div>
      <div>
        <h4>Services</h4>
        <ul>
          <li><a href="tempo-traveller-pune.html">Tempo Traveller hire</a></li>
          <li><a href="airport-transfer-pune-mumbai.html">Airport transfers</a></li>
          <li><a href="tour-packages.html">All India tour packages</a></li>
          <li><a href="index.html#pricing">Fare chart</a></li>
          <li><a href="index.html#book">Book online</a></li>
          <li><a href="index.html#faq">FAQ</a></li>
        </ul>
      </div>
    </div>
    <div class="footer__areas" style="padding-bottom:22px">
      <span>Pune</span><span>Mumbai</span><span>Lonavala</span><span>Nashik</span>
      <span>Shirdi</span><span>Mahabaleshwar</span><span>Alibaug</span><span>All India</span>
    </div>
    <div class="footer__bottom">
      © 2026 A1 Tour and Travels. Pune ↔ Mumbai Cabs &amp; Buses · Match Cabs · All India Tours · {PHONE_LOCAL}
    </div>
  </div>
</footer>

<a class="wa-float" href="{WA_LINK}?text=Hi%20A1%20Tour%20and%20Travels%2C%20I%20want%20to%20enquire%20about%20a%20booking."
   target="_blank" rel="noopener noreferrer" aria-label="Chat with A1 Tour and Travels on WhatsApp">
  <svg viewBox="0 0 24 24" fill="#fff" aria-hidden="true"><path d="M12.04 2a9.9 9.9 0 0 0-8.4 15.13L2.5 22l5.02-1.3A9.9 9.9 0 1 0 12.04 2zm5.77 14.06c-.24.68-1.4 1.3-1.94 1.35-.54.05-1.03.24-3.47-.72-2.94-1.16-4.79-4.19-4.94-4.38-.14-.19-1.16-1.55-1.16-2.96 0-1.4.73-2.09 1-2.37.24-.29.53-.36.72-.36l.51.01c.17 0 .39-.06.6.46.24.55.8 1.9.87 2.04.07.14.12.31.02.5-.1.19-.15.31-.29.48l-.43.5c-.14.14-.29.3-.12.58.16.29.73 1.2 1.56 1.95 1.07.95 1.9 1.25 2.18 1.39.29.14.46.12.63-.07.16-.19.72-.84.91-1.13.19-.29.39-.24.65-.15.26.1 1.66.79 1.95.93.29.15.48.22.55.34.07.13.07.79-.17 1.47z"/></svg>
</a>
</body>
</html>
'''


def main():
    out = pathlib.Path(__file__).parent
    written = []
    for p in PAGES:
        html = page(p)
        (out / p["slug"]).write_text(html, encoding="utf-8")
        written.append((p["slug"], len(html)))

    # sitemap: built by scanning what is actually published, so it can never
    # drift out of date when pages are added (404 and owner-only tools excluded)
    skip = {"404.html", "post-ads.html", "index.html"}
    published = sorted(f.name for f in out.glob("*.html") if f.name not in skip)
    urls = [("", "1.0", "weekly")] + [(u, "0.8", "monthly") for u in published]
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

    print(f"wrote {len(written)} pages:")
    for slug, size in written:
        print(f"  {slug:38} {size/1024:6.1f} KB")
    print(f"  sitemap.xml with {len(urls)} URLs")


if __name__ == "__main__":
    main()
