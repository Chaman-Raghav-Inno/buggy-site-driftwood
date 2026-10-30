"""Prices, availability and cancellation rules. The rules guests read are on /help (pages/help.html).

Two price paths exist: `quote` (the estimate on the listing page and the review step of checkout) and `charge`
(what a confirmed booking costs). Planted bugs are marked BUG-nn; see BUGS.md.
"""

import datetime as dt

from . import data

BASE_OCCUPANCY = 2
EXTRA_GUEST_FEE = 25.0  # per guest aged 13+ beyond 2, per night
PET_FEE = 40.0  # per stay
SERVICE_RATE = 0.12  # of the nights after discounts plus extra-guest fees; never refunded
HOST_FEE = 0.03
CHECK_IN_HOUR = 15
PROMOS = {
    "STAY15": {"rate": 0.15, "min_nights": 3, "expires": None},
    "SUMMER25": {"rate": 0.25, "min_nights": 1, "expires": "2026-09-30"},
}
POLICIES = {
    "flexible": "Full refund until 24 hours before check-in (3:00 PM local time). No refund after that.",
    "moderate": "Full refund until 5 days before check-in. After that, 50% of the nightly amount.",
    "strict": "50% of the nightly amount until 7 days before check-in. No refund after that.",
}


class PriceError(Exception):
    pass


def d(iso: str) -> dt.date:
    return dt.date.fromisoformat(iso)


def nights(check_in: str, check_out: str) -> list[dt.date]:
    start, end = d(check_in), d(check_out)
    return [start + dt.timedelta(days=i) for i in range((end - start).days)]


def is_weekend(night: dt.date) -> bool:
    return night.weekday() in (5, 6)  # BUG-12: weekend nights are Friday and Saturday (4, 5)


def stay_discount_rate(n: int) -> float:
    if n >= 28:
        return 0.20
    return 0.10 if n > 7 else 0.0  # BUG-13: the weekly discount starts at 7 nights


def occupancy(adults: int, ages: list[int]) -> int:
    """Guests counted against the listing's maximum: everyone but infants (under 2)."""
    return adults + sum(1 for a in ages if a >= 2)


def paying_guests(adults: int, ages: list[int]) -> int:
    """Guests who count for extra-guest fees: adults and children aged 13 and over."""
    return adults + sum(1 for a in ages if a >= 12)  # BUG-16: 12-year-olds are children (13 and over pay)


def promo_rate(code: str | None, n: int, today: dt.date, at_checkout: bool) -> float:
    if not code:
        return 0.0
    promo = PROMOS.get(code.strip().upper())
    if not promo:
        raise PriceError("That promo code isn't valid.")
    if n < promo["min_nights"]:
        raise PriceError(f"{code.upper()} needs a stay of {promo['min_nights']} nights or more.")
    if at_checkout and promo["expires"] and today.isoformat() > promo["expires"]:
        raise PriceError("expired")  # BUG-23: only checked when the booking is confirmed, not when applied
    return promo["rate"]


def _breakdown(listing: dict, trip: dict, today: dt.date, at_checkout: bool) -> dict:
    stay_nights = nights(trip["check_in"], trip["check_out"])
    n = len(stay_nights)
    lines = [(night.isoformat(), listing["weekend"] if is_weekend(night) else listing["base"]) for night in stay_nights]
    weekend = sum(1 for night in stay_nights if is_weekend(night))
    subtotal = float(sum(p for _, p in lines))
    discount = round(subtotal * stay_discount_rate(n), 2)
    stay = subtotal - discount
    extra_guests = max(0, paying_guests(trip["adults"], trip["ages"]) - BASE_OCCUPANCY)
    extra = extra_guests * EXTRA_GUEST_FEE * (n if at_checkout else 1)  # BUG-21: the estimate charges it once
    pet_fee = PET_FEE if trip["pets"] else 0.0
    cleaning = float(listing["cleaning"])
    service = round(SERVICE_RATE * (subtotal + extra), 2)  # BUG-14: should be the nights after the discount
    taxable = stay + extra + (cleaning if at_checkout else 0.0)  # BUG-15: the estimate leaves cleaning untaxed
    tax_rate = data.LOCATIONS[listing["city"]]["tax"]
    tax = round(taxable * tax_rate, 2)
    total = stay + extra + pet_fee + cleaning + service + tax
    rate = promo_rate(trip.get("promo"), n, today, at_checkout)
    promo = round(total * rate, 2)  # BUG-24: the code is for 15% off the nights, not the whole total
    return {
        "nights": n,
        "nightly": lines,
        "weekend_nights": weekend,
        "subtotal": round(subtotal, 2),
        "discount": discount,
        "discount_rate": stay_discount_rate(n),
        "extra_guests": extra_guests,
        "extra": round(extra, 2),
        "pets": pet_fee,
        "cleaning": cleaning,
        "service": service,
        "tax": tax,
        "tax_rate": tax_rate,
        "promo": promo,
        "promo_code": (trip.get("promo") or "").strip().upper() or None,
        "total": round(total - promo, 2),
    }


def quote(listing: dict, trip: dict, today: dt.date) -> dict:
    return _breakdown(listing, trip, today, at_checkout=False)


def charge(listing: dict, trip: dict, today: dt.date) -> dict:
    return _breakdown(listing, trip, today, at_checkout=True)


def booked_by_search(listing: dict, bookings: list[dict], check_in: str, check_out: str) -> bool:
    """Whether the dates clash with a booking or a blocked night (search, holds and date changes use this)."""
    wanted = {n.isoformat() for n in nights(check_in, check_out)}
    if wanted & set(listing["blocked"]):
        return True
    for b in bookings:  # BUG-33: cancelled bookings still count
        if b["listing"] == listing["id"] and b["check_in"] <= check_in < b["check_out"]:  # BUG-01: misses overlaps
            return True
    return False


def booked_days(listing: dict, bookings: list[dict]) -> list[str]:
    """Days the listing page's calendar shows as taken."""
    days = set(listing["blocked"])
    for b in bookings:  # BUG-33: cancelled bookings still count
        if b["listing"] != listing["id"]:
            continue
        start, end = d(b["check_in"]), d(b["check_out"])
        for i in range((end - start).days + 1):  # BUG-08: the check-out day is free for the next guest
            days.add((start + dt.timedelta(days=i)).isoformat())
    return sorted(days)


def deadline(listing: dict, check_in: str, days_before: int) -> dt.datetime:
    """When a policy step ends: `days_before` days before check-in at 3:00 PM at the listing."""
    day = d(check_in) - dt.timedelta(days=days_before)
    return dt.datetime.combine(day, dt.time(CHECK_IN_HOUR), tzinfo=dt.UTC)  # BUG-29: should be the listing's time


def local(listing: dict, moment: dt.datetime) -> str:
    loc = data.LOCATIONS[listing["city"]]
    t = moment.astimezone(dt.timezone(dt.timedelta(hours=loc["offset"])))
    return f"{t.strftime('%b')} {t.day}, {t.strftime('%I:%M %p').lstrip('0')} ({loc['zone']})"


def refund(listing: dict, booking: dict, now: dt.datetime) -> dict:
    """What cancelling now gives back, and until when the current terms hold."""
    p = booking["price"]
    nights_amount = p["subtotal"] - p["discount"] + p["extra"]
    everything = p["total"]  # BUG-30: the service fee is never refunded
    policy = listing["policy"]
    if policy == "flexible":
        steps = [(deadline(listing, booking["check_in"], 1), everything, "Full refund")]
    elif policy == "moderate":
        steps = [(deadline(listing, booking["check_in"], 5), everything, "Full refund")]
        steps.append((deadline(listing, booking["check_in"], 0), round(nights_amount * 0.5, 2), "50% of the nights"))
    else:
        steps = [(deadline(listing, booking["check_in"], 7), round(nights_amount * 0.5, 2), "50% of the nights")]
    for until, amount, label in steps:
        if now < until:
            return {"amount": round(amount, 2), "label": label, "until": local(listing, until)}
    return {"amount": 0.0, "label": "No refund", "until": None}
