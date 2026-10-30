# Driftwood Stays: answer key (40 planted bugs)

Driftwood Stays is a holiday-rental booking site (search, listings, checkout, trips, wishlist, host dashboard)
with **functional bugs planted on purpose**, for checking what the AI QA Scanner finds. It is the hardest of the
three benchmark sites: only 8 bugs are Medium; the rest need date and pricing rules, arithmetic, two pages compared,
a role switch, a reload, a race, or a non-English value.

This file is never served, and nothing the site serves (pages, scripts, CSS, images) names or hints at a bug.
Server-side code marks each one with a `BUG-nn` comment; `tests/test_driftwood.py` keeps the server-side ones in
place. The rules every bug breaks are published on the site's **How pricing works** page (`/help`) and on each
listing page, so a scanner can know the expected behaviour.

## Run it

- **Locally**: `python -m driftwood` (port 8082, or `PORT`), then open http://localhost:8082.
- **Railway**: New service → GitHub repo → this repository, then **Generate domain**. `railway.json` sets the start
  command and health check; no variables or volume needed.

Every visitor (cookie) gets a private copy of the demo world, dated around today, so parallel scans never see each
other's changes and a new browser session starts from the original data. A restart resets everything.

## Test data

Days below are counted from the day the session starts ("day 0" is today, UTC).

| What | Value |
|---|---|
| Accounts (password `Driftwood@2026`, listed on the login page) | `gina@driftwood.test` guest · `hal@driftwood.test` host of Lanikai Beach Cottage, Shibuya Sky Apartment and Harbour View Flat |
| Listings | 9: Honolulu (Lanikai Beach Cottage, Diamond Head Studio, North Shore Surf House), Tokyo (Shibuya Sky Apartment, Asakusa Machiya House, Ginza Capsule Loft), Reykjavík (Harbour View Flat, Aurora Glass Cabin, Lava Field Guest Room). Ginza and Lava Field have no reviews ("New") |
| Gina's trips | DW-4721 Shibuya, day 3 to 6 (Flexible) · DW-4758 Lanikai, day 0 to 4 (checks in today) · DW-4795 Harbour View, day 20 to 25 (Moderate) · DW-4832 Aurora and DW-4869 Diamond Head, past stays |
| Other guests' bookings | Lanikai day 10 to 13 (Ravi) · Harbour View day 8 to 10 · Shibuya day 12 to 16 · Aurora day 5 to 9 |
| Lanikai Beach Cottage | $180 Sun–Thu nights, $240 Fri–Sat nights, $90 cleaning, sleeps 4, 1 pet, minimum 2 nights, Moderate, Honolulu tax 13.96%, reviews average 4.857 |
| Promo codes | `STAY15` (15% off the nights, 3+ nights) · `SUMMER25` (expired) |
| Currencies | USD, EUR (0.9187) and JPY (151.37), chosen in the header |

Difficulty: **Medium** needs a flow or a comparison; **Hard** needs the published rules, a second page, a reload,
a role switch or an edge-case value; **Expert** needs arithmetic across several numbers, a race, a time zone, a
browser reload of a form post, or a sequence of steps in one tab.

## The bugs

### Search

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-01 | Search misses bookings inside your dates | Search Honolulu, day 9 to day 14 | Lanikai not listed (booked day 10 to 13) | Lanikai is listed; only bookings that cover your check-in day count, so a booking inside your stay is missed (and a crafted `/book` link double-books it) | Critical | Expert | `pricing.py` `booked_by_search` |
| BUG-02 | Children don't count towards a stay's size | Search Tokyo, 2 adults + 2 children (ages 8, 10) | Only stays for 4+ (Asakusa) | Shibuya Sky (sleeps 3) is listed too | Medium | Medium | `server.py` `Store.search` |
| BUG-03 | Price filter ignores weekend rates | Search Honolulu, a Friday 4+ weeks out for 2 nights, Price "Up to $200" | Lanikai not listed (its nights average $210) | Listed at "$210.00 a night"; the filter checks the weekday rate only | Medium | Hard | `server.py` `Store.search` |
| BUG-04 | Rating sort puts new stays first | Sort by Guest rating | Highest rated first (Lanikai 4.86, Shibuya 4.8…) | Lava Field / Ginza ("New", no reviews) come first | Medium | Hard | `server.py` `Store.search` |
| BUG-05 | Results can belong to an older filter | Tick Pets allowed, then untick it within about a second | All 8–9 stays | After a moment the 3 pet-friendly stays replace them, with the box unticked (the slower pets request lands last) | High | Expert | `static/search.js` `load` (no stale-response check); `server.py` slow pets search |
| BUG-06 | A stay of 0 nights can be booked | Listing page: same date for check-in and check-out | "Check-out must be after check-in" | Estimate shows just the cleaning fee, and Reserve → checkout books 0 nights | High | Medium | `static/listing.js` `problem`; `server.py` `trip_from` |
| BUG-07 | Children are lost when opening a stay from results | Search Tokyo, 2 adults + 1 child (13) → open Shibuya | Widget shows the child; estimate includes the extra guest | Widget shows 0 children (adults and dates carry over) | Medium | Hard | `static/listing.js` (ignores `ages`) |

### Listing page

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-08 | You can't check in on another guest's check-out day | Lanikai, check in on day 13 (Ravi checks out) for 2 nights | Allowed (rules: check-out 11 AM, check-in 3 PM; "You can check in on the day another guest checks out") | "Those dates aren't available"; the calendar shows day 13 taken | High | Hard | `pricing.py` `booked_days` |
| BUG-09 | Rating differs between search and listing | Lanikai in results vs its page | Same rating | Card "★ 4.8" (truncated), page "★ 4.9" (rounded) | Low | Hard | `static/core.js` `D.card` |
| BUG-10 | Minimum stay is not enforced when booking | Lanikai (minimum 2 nights) for 1 night → Reserve | Refused | Estimate and booking go through | High | Hard | `static/listing.js`; `server.py` `trip_from` (only search checks it) |
| BUG-11 | Pet limit is not enforced | Harbour View (up to 1 pet), Pets: 2 | Refused | Accepted, one $40 pet fee | Medium | Medium | `static/listing.js` (offers 0–3); `server.py` `trip_from` |

### Prices

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-12 | Wrong nights are charged as weekend | Lanikai, check in on a Friday for 2 nights | 2 weekend nights × $240 (Friday and Saturday) | "1 weekday night × $180, 1 weekend night × $240": Saturday and Sunday are treated as the weekend | High | Hard | `pricing.py` `is_weekend` |
| BUG-13 | Weekly discount starts a night late | 7 nights vs 8 nights | 10% off from 7 nights | No discount at 7; 10% from 8 | High | Hard | `pricing.py` `stay_discount_rate` |
| BUG-14 | Service fee ignores the stay discount | 8 nights at Lanikai | 12% of the nights after the discount | 12% of the nights before it (e.g. $187.20 on $1,560, not $168.48 on $1,404) | Medium | Expert | `pricing.py` `_breakdown` |
| BUG-15 | The estimate taxes less than the booking | Same stay: listing estimate, review step, then confirm | Same total everywhere | Estimate and review leave the cleaning fee untaxed; the confirmed booking costs ≈ $12.56 more at Lanikai (13.96% of $90) | High | Hard | `pricing.py` `_breakdown` |
| BUG-16 | A 12-year-old pays as an adult | Lanikai, 2 adults + 1 child aged 12 | No extra-guest fee (children 2–12 stay free) | "Extra guests (1)" | Medium | Hard | `pricing.py` `paying_guests` |
| BUG-17 | Euro and yen prices don't add up | Header currency ¥ JPY (or € EUR), Lanikai 2 nights | Lines add up to the total | Lines add to e.g. ¥93,700 while the total says ¥93,702 (every amount is truncated, not rounded) | Low | Expert | `static/core.js` `D.convert` |

### Checkout

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-18 | Back clears your details | Fill Your details → Continue → Back | Details still filled | Name, phone, arrival and requests are empty | Medium | Medium | `static/book.js` `stepDetails` |
| BUG-19 | Real names are refused | Full name `Seán O'Brien` (or `José`, `Anne-Marie`) | Accepted | "Enter your full name using letters only." | High | Medium | `static/book.js` `NAME` |
| BUG-20 | Special requests over 500 bytes fail | Special requests: 300 × `é` (counter 300 / 500) → Review | Accepted | "Special requests can be at most 500 characters." (the server counts bytes) | Low | Expert | `server.py` `Store.hold` |
| BUG-21 | Extra guests cost more than the review said | Lanikai, 3 adults, 3 nights → review → confirm | Review and charge agree ($25 × 3 nights) | Review: extra guests $25 (once); charged $75 + tax more (e.g. review $952.83, charged $1,028.37) | High | Hard | `pricing.py` `_breakdown` |
| BUG-22 | Review step shows euros but dollar numbers | Currency € EUR → book → Review | Converted amounts (as on the listing page) | "€" in front of the USD amounts (e.g. €610.57 where the listing page said €560.93) | Medium | Hard | `static/book.js` `stepReview` |
| BUG-23 | An expired code is accepted, then the booking fails | Payment: promo `SUMMER25` → Apply → Review → Confirm | "This code has expired" at Apply | "SUMMER25 applied: −$…", then Confirm → "Something went wrong" → Start again loses every detail, guest and pet | High | Hard | `pricing.py` `promo_rate`; `server.py` confirm |
| BUG-24 | STAY15 discounts the whole bill | STAY15 on a 3-night Shibuya stay ($450 of nights) | −$67.50 (15% of the nights) | 15% of the total with fees and taxes (e.g. −$91.59) | Medium | Expert | `pricing.py` `_breakdown` |
| BUG-25 | Reloading the confirmation books again | Confirm a booking, then reload the confirmation page (or click Confirm twice) | One booking | A second booking with a new reference, charged again | Critical | Expert | `server.py` `Store.confirm` (hold never used up) |

### Trips

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-26 | Today's stay is filed under Past | Trips → Past | Lanikai (checks in today) under Upcoming | Under Past | Medium | Hard | `server.py` `Store.trips` |
| BUG-27 | You can review a stay before it happens | Upcoming trip DW-4721 → Write a review | Not offered until the stay ends | Offered and posted to the listing | Medium | Medium | `server.py` `Store.review`; `static/trip.js` |
| BUG-28 | Changing dates keeps the old price | DW-4795: change check-out from day 25 to day 27 | Re-priced (rules: "Changing your dates re-prices your stay") | 7 nights for the 5-night price | High | Hard | `server.py` `Store.change` |
| BUG-29 | Free-cancellation deadline is in the wrong time zone | DW-4721 (Tokyo, Flexible, check-in day 3) | "until day 2, 3:00 PM (Tokyo time)" | "until day 3, 12:00 AM (Tokyo time)": 3 PM UTC; Honolulu deadlines are 10 hours early; refunds follow it | High | Expert | `pricing.py` `deadline` |
| BUG-30 | Refunds include the service fee | DW-4795 (Moderate, 20 days out) → Cancel trip | Total minus the service fee (e.g. $92.40) | The whole total (e.g. $1,012.28) offered and refunded | High | Hard | `pricing.py` `refund` |
| BUG-31 | Receipt total differs from the trip | DW-4721 / DW-4758 / DW-4795 → View receipt | Same total | Receipt is 1 cent less (tax rounded per line); depends on the nights | Low | Expert | `server.py` `receipt_page` |
| BUG-32 | Removing from the wishlist doesn't, and saving again duplicates | Heart a stay, un-heart it, heart it again → Wishlist | Saved once (or not at all after un-hearting) | Listed twice (un-hearting never removed it) | Medium | Hard | `server.py` `Store.wish` (compares text with a number) |
| BUG-33 | Cancelled trips still block the dates | Cancel DW-4795 → search Reykjavík day 21 to 23 | Harbour View available again | Not listed; its calendar still shows the nights taken | High | Hard | `pricing.py` `booked_by_search`, `booked_days` |

### Host dashboard (log in as Hal)

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-34 | A price with a thousands comma is saved as $1 | Edit Lanikai → weekday price `1,250` → Save | $1,250 (or "Enter a number") | "Saved. Weekdays $1.00" | High | Hard | `static/host-listing.js` (`parseFloat`) |
| BUG-35 | Blocking dates misses the last night | Block day 40 "through" day 42 | 3 nights blocked | 2 (day 40 and 41) | Medium | Hard | `static/host-listing.js` |
| BUG-36 | Blocking dates undoes a price change | Change weekday price to 200 → Save → Block any dates → reload | 200 | Back to 180 (the block form sends the listing as it was when the page opened) | High | Expert | `static/host-listing.js` |
| BUG-37 | A minimum stay of 0 nights is accepted | Minimum stay 0 → Save | Refused (at least 1) | Saved; listing says "Minimum stay: 0 nights" | Low | Medium | `server.py` `save_listing` |
| BUG-38 | Payouts include taxes and the service fee | Reservations table: Guest paid vs Your payout | Nights + fees + cleaning − 3% (dashboard text says so) | 97% of everything the guest paid | High | Hard | `server.py` `Store.host` |
| BUG-39 | Occupancy counts check-out days | Occupancy, next 30 days | Booked nights ÷ 90 (e.g. 23%) | Higher (e.g. 30%): each check-out day counts as a night | Medium | Hard | `server.py` `Store.host` |

### Error handling

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-40 | An unknown stay hangs on "Loading…" | Open `/listing?id=999` | "We couldn't find that stay" | "Loading…" forever and a JavaScript error ("Cannot read properties of undefined") | Medium | Medium | `static/listing.js` (no check on the response) |

## What is not a planted bug

- Console errors that come with a bug: 400 from `/api/holds` (BUG-20), 500 from `/book/confirm` (BUG-23), 404 and
  the JavaScript error on an unknown listing (BUG-40), 404 on unknown pages.
- Date pickers show dates in the browser's format, whatever the currency.
- Server-rendered pages (confirmation, receipt) are in US dollars and say so.
- Each visitor has a private world: changes in one browser session do not show in another.
- "Demo booking site for QA testing" in the footer and the demo accounts on the login page.

By area: search 7, listing page 4, prices 6, checkout 8, trips 8, host 6, error handling 1.
By difficulty: Medium 8, Hard 22, Expert 10. By severity: Critical 2, High 17, Medium 16, Low 5.
