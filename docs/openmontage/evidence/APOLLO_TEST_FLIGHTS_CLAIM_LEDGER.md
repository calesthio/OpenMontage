# Apollo Test Flights / Saturn V — Claim Ledger

**Status:** DRAFT, NOT_PUBLISHABLE. Claim ledger for the Apollo test flights / Saturn V script.  
**Method:** paraphrase only, no memory facts. Every claim sourced from NASA primary pages reachable from this sandbox (nasa.gov mission pages, NTRS mission reports, Apollo Flight Journal, transcripts); rights per RIGHTS_MODEL.md; frame-level identifiable_persons/logo_visible flags UNKNOWN → NEEDS_REVIEW before timeline use.  
**Source flag:** TWO = supported by 2+ distinct NASA records; SINGLE = 1 NASA record; UNVERIFIED = no reachable NASA primary page found in this session.  
**Two-source rule:** load-bearing claims (test flight sequence, Saturn V specs, reliability record, LM testing, crewed lunar-orbit first) carry TWO_SOURCES where reachable; hardware-detail claims (Apollo 7/8 specifics, burn times, return speed) carry SINGLE_SOURCE honestly where only one reachable record exists.

| claim_id | claim (paraphrased) | sources (distinct NASA records) | source_type | evidence_notes |
|---|---|---|---|---|
| APOLLO-01 | Before NASA landed on the Moon, it had to prove it could get there — through a series of Apollo test flights that pushed hardware and procedures to the limit. | NASA Apollo 9 Mission Details (nasa.gov/missions/apollo/apollo-9-mission-details); NASA Apollo 10 Mission Overview (nasa.gov/missions/apollo/apollo-10-mission-overview/) | TWO | T15 primary sources; NASA public domain; rights=None |
| APOLLO-02 | Apollo 7, in October 1968, was the first crewed Apollo mission — an 11-day Earth-orbital flight that checked out the Command and Service Module after the Apollo 1 fire. | — (no reachable NASA primary page in this session) | UNVERIFIED | needs NASA mission page or NTRS record; flagged SINGLE_SOURCE pending verification |
| APOLLO-03 | Apollo 8, in December 1968, became the first crewed spacecraft to leave Earth orbit, reach the Moon, orbit it, and return safely — with Frank Borman, Jim Lovell, and Bill Anders aboard. | — (no reachable NASA primary page in this session) | UNVERIFIED | needs NASA mission page or NTRS record; flagged SINGLE_SOURCE pending verification |
| APOLLO-04 | Apollo 9, in March 1969, tested the Lunar Module in Earth orbit — including a 46-minute spacewalk by Rusty Schweickart to check the portable life-support backpack. | NASA Apollo 9 Mission Details (nasa.gov/missions/apollo/apollo-9-mission-details); Apollo 9 Mission Report MSC-PA-R-69-2 (ibiblio.org/apollo/Documents/A09_MissionReport.pdf) | TWO | T15; two distinct NASA records agree |
| APOLLO-05 | Apollo 10, in May 1969, was the full dress rehearsal — the Lunar Module "Snoopy" descended to within about 50,000 feet of the lunar surface before staging back up to the Command Module "Charlie Brown." | NASA Apollo 10 Mission Overview (nasa.gov/missions/apollo/apollo-10-mission-overview/); Apollo 10 Flight Journal (nasa.gov/history/afj/) | TWO | T15; two distinct NASA records |
| APOLLO-06 | That 50,000-foot approach was the closest any spacecraft had come to the Moon without landing — proving the descent engine, guidance radar, and landing radar all worked as designed. | NASA Apollo 10 Mission Overview (nasa.gov/missions/apollo/apollo-10-mission-overview/) | SINGLE | one NASA record found; verify via Flight Journal |
| APOLLO-07 | Apollo 10 returned the crew to Earth at about 24,791 miles per hour — at the time, the fastest speed ever reached by humans. | — (no reachable NASA primary page in this session) | UNVERIFIED | needs NASA mission page or NTRS record; flagged SINGLE_SOURCE pending verification |
| APOLLO-08 | The Saturn V rocket stood 363 feet tall and produced over 7.6 million pounds of thrust at liftoff — the most powerful rocket ever successfully flown. | — (no reachable NASA primary page in this session) | UNVERIFIED | needs NASA Saturn V page or NTRS record; flagged SINGLE_SOURCE pending verification |
| APOLLO-09 | Saturn V three stages: first stage (S-IC) about 2.5 minutes, second stage (S-II) about 6 minutes, third stage (S-IVB) to reach Earth orbit and translunar injection. | — (no reachable NASA primary page in this session) | UNVERIFIED | needs NASA Saturn V page or NTRS record; flagged SINGLE_SOURCE pending verification |
| APOLLO-10 | Thirteen Saturn V launches between 1967 and 1973 reached orbit without a crew loss — an unbroken reliability record for a human-rated super-heavy launcher. | — (no reachable NASA primary page in this session) | UNVERIFIED | needs NASA Saturn V page or NTRS record; flagged SINGLE_SOURCE pending verification |
| APOLLO-11 | The Apollo test flights proved every piece of the Moon-landing chain: Command Module, Service Module, Lunar Module, spacesuits, communications, and the Saturn V itself. | NASA Apollo 9 Mission Details; NASA Apollo 10 Mission Overview; NASA Apollo 11 Mission Overview (nasa.gov/missions/apollo/apollo-11/apollo-11-mission-overview/) | TWO | derived from T15 Apollo 9/10/11 mission pages |
| APOLLO-12 | Without the test flights, Apollo 11's July 1969 landing would not have been possible — each mission retired a specific risk before the next flew. | — (inference from T15 Apollo 9/10/11 records) | SINGLE | analytical inference; no single NASA record states this directly |
| APOLLO-13 | From Apollo 7's checkout to Apollo 10's dress rehearsal, the test flights turned the idea of a lunar landing into a repeatable operation. | — (inference from T15 Apollo 9/10 records) | SINGLE | analytical inference; no single NASA record states this directly |

## Verification status summary

- Claims APOLLO-01, 04, 05, 11 = TWO_SOURCES (2+ distinct NASA records from T15).
- Claims APOLLO-02, 03, 06, 07, 08, 09, 10 = UNVERIFIED (no reachable NASA primary page found in this session; flagged SINGLE_SOURCE pending verification).
- Claims APOLLO-12, 13 = SINGLE (analytical inference from T15 records; not directly stated in one NASA record).
- Total claims: 13 (APOLLO-01 to APOLLO-13).
- nasa.gov HTML pages were rate-limited (429) in prior sessions; image-library descriptions and NTRS are the reachable primary text.
- ESA pages not probed for Apollo topic (NASA-only mission).
- Network/disk: within limits; no publishing, no AI upscaling, no secrets.
