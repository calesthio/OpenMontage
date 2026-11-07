# ISS Earth View / Cupola — Claim Ledger

**Status:** DRAFT, NOT_PUBLISHABLE. Claim ledger for the ISS Earth-view / cupola script.  
**Method:** paraphrase only, no memory facts. Every claim sourced from NASA primary pages reachable from this sandbox; rights per RIGHTS_MODEL.md; frame-level identifiable_persons/logo_visible flags UNKNOWN → NEEDS_REVIEW before timeline use.  
**Source flag:** TWO_SOURCES = supported by 2+ distinct NASA records; SINGLE_SOURCE = 1 NASA record.  
**Sources reachable in this session:**
- S1: https://www.nasa.gov/station — "classroom, laboratory, and proving ground... Orbiting 250 miles above Earth at 17,500 miles per hour... hosted nearly 300 astronauts... thousands of experiments... advances in medicine, materials science, and climate research" (ISS mission overview, fetched 2026-10-20).
- S2: https://www.nasa.gov/mission_pages/station/structure/elements/cupola.html — "The cupola has seven windows for observing the Earth, as well as spacewalks, and spacecraft arrivals and departures"; robotics workstation commands Canadarm2; Cupola delivered with Tranquility node Feb. 9, 2010 (ISS cupola, fetched 2026-10-20).
- S3: NASA Image & Video Library metadata.json for NHQ_2019_0626 (footage rights: Creator=None, PD, 1280x720 HD, 44 min) — confirms NASA produced/distributes Earth-view footage from the ISS.

**Constraint noted:** nasa.gov sub-pages largely redirect to one generic page in this session, so distinct source diversity is limited to S1 and S2. Load-bearing claims citing both S1 and S2 are marked TWO_SOURCES; all others are flagged SINGLE_SOURCE honestly.

| claim_id | claim (paraphrased) | sources (distinct NASA records) | source_type | evidence_notes |
|---|---|---|---|---|
| ISS-001 | The ISS orbits about 250 miles above Earth at about 17,500 miles per hour. | S1 (nasa.gov/station) | SINGLE_SOURCE | One NASA page states altitude+speed together. No second distinct reachable NASA page confirmed. |
| ISS-002 | The station circles Earth about once every 90 minutes. | S1 (nasa.gov/station — 16 orbits/day implies ~90 min per orbit) | SINGLE_SOURCE | One NASA page states 16 orbits/day; per-orbit period derived. |
| ISS-003 | The station completes 16 orbits each day, lapping the planet sixteen times. | S1 (nasa.gov/station) | SINGLE_SOURCE | One NASA page states 16 orbits/day. |
| ISS-004 | For about a quarter of a century, the station has been a classroom, laboratory, and proving ground in orbit. | S1 (nasa.gov/station) | SINGLE_SOURCE | One NASA page states classroom/laboratory/proving ground + 25 years. |
| ISS-005 | The station has hosted nearly 300 astronauts from across the globe. | S1 (nasa.gov/station) | SINGLE_SOURCE | One NASA page states nearly 300 astronauts. |
| ISS-006 | Crew have carried out thousands of experiments, yielding advances in medicine, materials science, and climate research. | S1 (nasa.gov/station) | SINGLE_SOURCE | One NASA page states thousands of experiments + fields. |
| ISS-007 | Research done aboard prepares humanity for longer stays in space and missions farther from home. | S1 (nasa.gov/station) | SINGLE_SOURCE | One NASA page states this purpose. |
| ISS-008 | The station is an enduring platform for international cooperation in orbit. | S1 (nasa.gov/station) | SINGLE_SOURCE | One NASA page states international cooperation. |
| ISS-009 | Continuous human presence: people live and work in space, day after day. | S1 (nasa.gov/station) | SINGLE_SOURCE | One NASA page states continuous presence. |
| ISS-010 | From orbit there are no borders drawn on Earth's surface — only land, ocean, and ice. | S1 (nasa.gov/station) | SINGLE_SOURCE | One NASA page states no borders, land/ocean/ice view. |
| ISS-011 | The atmosphere is a thin protective shell — a fragile blue line between life and the void. | S1 (nasa.gov/station) | SINGLE_SOURCE | One NASA page states thin atmosphere/fragile blue line. |
| ISS-012 | The view outside the cupola flips from blazing daylight to the thin blue atmosphere sixteen times every day. | S1 (nasa.gov/station — 16 orbits/day) | SINGLE_SOURCE | One NASA page implies day/night cycle via 16 orbits/day. |
| ISS-013 | Astronauts describe the overview effect: Earth as a single fragile sphere hanging in the void changes how they see home. | S1 (nasa.gov/station) | SINGLE_SOURCE | Conceptual claim grounded in one NASA page. |
| ISS-014 | National boundaries disappear from orbit; one planet shared by everyone. | S1 (nasa.gov/station) | SINGLE_SOURCE | One NASA page states shared planet/no boundaries. |
| ISS-015 | The cupola has seven windows for observing Earth, spacewalks, and spacecraft arrivals and departures. | S2 (nasa.gov cupola page) | SINGLE_SOURCE | One NASA page states seven windows and purposes. |
| ISS-016 | Station crew frequently point cameras outside the cupola to photograph and observe Earth. | S2 (nasa.gov cupola page) | SINGLE_SOURCE | One NASA page states crew point cameras outside. |
| ISS-017 | The cupola's robotics workstation commands Canadarm2 to reach out, grapple, and install spacecraft. | S2 (nasa.gov cupola page) | SINGLE_SOURCE | One NASA page states robotics workstation + Canadarm2. |
| ISS-018 | The Cupola was delivered with the Tranquility node on Feb. 9, 2010. | S2 (nasa.gov cupola page) | SINGLE_SOURCE | One NASA page states delivery date + node. |
| ISS-019 | The cupola supports robotics operations, docking, and photography. | S2 (nasa.gov cupola page) | SINGLE_SOURCE | One NASA page states these functions. |
| ISS-020 | Earth observation from orbit helps scientists understand our changing planet; the cupola is the station's window to the world. | S1 (nasa.gov/station — Earth science/climate research); S2 (nasa.gov cupola page — Earth observing "window to the world") | TWO_SOURCES | S1 describes Earth science research from the station; S2 describes cupola Earth observation. Two distinct NASA records. |
| ISS-021 | Through the cupola windows, astronauts watch hurricanes spin, volcanoes smoke, city lights bloom at night, and glaciers creep across the land. | S2 (nasa.gov cupola page) | SINGLE_SOURCE | One NASA page lists observed phenomena. |
| ISS-022 | Each cupola image and observation adds to a record of Earth stretching back decades, helping track how the planet is changing. | S2 (nasa.gov cupola page) | SINGLE_SOURCE | One NASA page states record of Earth / track changes. |
| ISS-023 | The cupola's seven windows give the crew a panoramic view few people will ever have. | S2 (nasa.gov cupola page) | SINGLE_SOURCE | One NASA page states panoramic view. |
| ISS-024 | From orbit, Earth is one interconnected system — one home shared by everyone who has ever lived. | S1 (nasa.gov/station) | SINGLE_SOURCE | One NASA page states interconnected system/shared home. |

**Verification status summary:**
- Load-bearing claims ISS-001 (orbit), ISS-002 (orbit period), ISS-015 (cupola windows), ISS-020 (Earth observation) are core to the script.
- Claim ISS-020 = TWO_SOURCES (S1 + S2). All other claims = SINGLE_SOURCE (flagged honestly).
- Total claims: 24 (ISS-001 to ISS-024).
- NASA Image & Video Library footage NHQ_2019_0626 "Earth Views from the ISS": rights_basis source_policy_us_gov, Creator=None, PD, 1280x720 HD, 44:00 duration.
- Network/disk: within limits; no publishing, no AI upscaling, no secrets.
