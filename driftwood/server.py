"""Driftwood Stays: holiday rentals with planted functional bugs, for checking what the AI QA Scanner finds.

The bugs are listed in BUGS.md (the answer key), which is never served. Comments marking a planted bug (BUG-nn)
only appear in server-side code; the pages and scripts the scanner reads carry none.

Each visitor (cookie) gets a private copy of the demo world (listings, bookings, accounts), kept in memory, so
parallel scans never see each other's changes. A restart starts every world afresh.
"""

import datetime as dt
import hmac
import html
import json
import os
import re
import secrets
import threading
import time
from collections import OrderedDict
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from . import data, pricing

HERE = Path(__file__).resolve().parent
PAGES_DIR = HERE / "pages"
STATIC_DIR = HERE / "static"
STATIC_TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"
    ),
}
MAX_BODY = 64 * 1024
MAX_SESSIONS = 2000
MAX_REQUEST_BYTES = 500
SLOW_SEARCH_SECONDS = 1.5
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
CURRENCIES = ("USD", "EUR", "JPY")
HOSTS = {2: "Hal", 3: "Mele"}

# path -> (page, title, who may open it)
PAGES = {
    "/": ("home", "Holiday homes in Honolulu, Tokyo and Reykjavík", None),
    "/search": ("search", "Search stays", None),
    "/listing": ("listing", "Stay", None),
    "/help": ("help", "How pricing works", None),
    "/login": ("login", "Log in", None),
    "/book": ("book", "Book your stay", "guest"),
    "/trips": ("trips", "Your trips", "guest"),
    "/trip": ("trip", "Trip details", "guest"),
    "/wishlist": ("wishlist", "Wishlist", "guest"),
    "/host": ("host", "Host dashboard", "host"),
    "/host/listing": ("host-listing", "Edit listing", "host"),
}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _text(body: dict, key: str, limit: int = 200) -> str:
    value = body.get(key, "")
    return value.strip()[:limit] if isinstance(value, str) else ""


def _int(value, default: int, low: int, high: int, message: str) -> int:
    if value in (None, ""):
        return default
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ApiError(400, message) from None
    if not low <= n <= high:
        raise ApiError(400, message)
    return n


def _date(value, message: str = "Choose your dates.") -> str:
    if not isinstance(value, str):
        raise ApiError(400, message)
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError:
        raise ApiError(400, message) from None


def _ages(value) -> list[int]:
    if value in (None, "", []):
        return []
    items = value if isinstance(value, list) else str(value).split(",")
    ages = []
    for item in items[:6]:
        ages.append(_int(item, 0, 0, 17, "Children's ages are 0 to 17."))
    return ages


def rating(listing: dict) -> float | None:
    stars = [r["stars"] for r in listing["reviews"]]
    return round(sum(stars) / len(stars), 3) if stars else None


def money(amount: float) -> str:
    return f"${amount:,.2f}"


class Store:
    """Sessions, each with its own world."""

    def __init__(self):
        self.lock = threading.Lock()
        self.sessions: OrderedDict[str, dict] = OrderedDict()

    def session(self, sid: str | None) -> tuple[str, dict]:
        if sid and sid in self.sessions:
            self.sessions.move_to_end(sid)
            return sid, self.sessions[sid]
        sid = secrets.token_urlsafe(24)
        self.sessions[sid] = {"world": None, "user": None, "currency": "USD"}
        while len(self.sessions) > MAX_SESSIONS:
            self.sessions.popitem(last=False)
        return sid, self.sessions[sid]

    @staticmethod
    def world(sess: dict) -> dict:
        if sess["world"] is None:
            w = data.world(today(), time.time())
            for b in w["bookings"]:
                b["price"] = pricing.charge(Store.listing(w, b["listing"]), b, today())
            sess["world"] = w
        return sess["world"]

    @staticmethod
    def listing(w: dict, lid) -> dict:
        found = next((x for x in w["listings"] if x["id"] == lid), None)
        if not found:
            raise ApiError(404, "We couldn't find that stay.")
        return found

    def user(self, sess: dict) -> dict | None:
        if sess["user"] is None:
            return None
        return next((u for u in self.world(sess)["users"] if u["id"] == sess["user"]), None)

    def signed_in(self, sess: dict, role: str | None = None) -> tuple[dict, dict]:
        user = self.user(sess)
        if not user:
            raise ApiError(401, "Please log in.")
        if role and user["role"] != role:
            raise ApiError(403, "That page is for hosts." if role == "host" else "That is for guests.")
        return self.world(sess), user

    def me(self, sess: dict) -> dict:
        user = self.user(sess)
        public = {k: user[k] for k in ("id", "name", "email", "role")} if user else None
        return {"user": public, "currency": sess["currency"], "today": today().isoformat()}

    # browsing

    def card(self, sess: dict, listing: dict, trip: dict | None) -> dict:
        w = self.world(sess)
        out = {k: listing[k] for k in ("id", "name", "city", "type", "base", "weekend", "max_guests", "max_pets")}
        out |= {"min_nights": listing["min_nights"], "rating": rating(listing), "reviews": len(listing["reviews"])}
        out |= {"country": data.LOCATIONS[listing["city"]]["country"], "saved": listing["id"] in w["wishlist"]}
        out["image"] = f"/static/stay-{listing['id']}.svg"
        if trip:
            q = pricing.quote(listing, trip, today())
            out |= {"nights": q["nights"], "total": q["total"]}
            out["avg"] = round(q["subtotal"] / q["nights"], 2) if q["nights"] else 0.0
        return out

    def search(self, sess: dict, query: dict) -> dict:
        w = self.world(sess)
        arg = {k: (query.get(k) or [""])[0] for k in query}
        location = arg.get("location", "")
        adults = _int(arg.get("adults"), 2, 1, 16, "Choose 1 to 16 adults.")
        ages = _ages(arg.get("ages"))
        pets = arg.get("pets") == "1"
        max_price = _int(arg.get("max_price"), 0, 0, 100000, "Choose a price.")
        types = [t for t in arg.get("types", "").split(",") if t]
        trip = None
        if arg.get("check_in") and arg.get("check_out"):
            check_in, check_out = _date(arg["check_in"]), _date(arg["check_out"])
            if check_out < check_in:  # BUG-06: a stay needs at least one night
                raise ApiError(400, "Check-out must be after check-in.")
            trip = {"check_in": check_in, "check_out": check_out, "adults": adults, "ages": ages, "pets": int(pets)}
        results = []
        for listing in w["listings"]:
            if location and listing["city"] != location:
                continue
            if adults > listing["max_guests"]:  # BUG-02: children aged 2+ count towards the maximum too
                continue
            if pets and not listing["max_pets"]:
                continue
            if types and listing["type"] not in types:
                continue
            if max_price and listing["base"] > max_price:  # BUG-03: compares the weekday rate, not the dates' rate
                continue
            if trip:
                if len(pricing.nights(trip["check_in"], trip["check_out"])) < listing["min_nights"]:
                    continue
                if pricing.booked_by_search(listing, w["bookings"], trip["check_in"], trip["check_out"]):
                    continue
            results.append(self.card(sess, listing, trip))
        sort = arg.get("sort", "")
        if sort == "price":
            results.sort(key=lambda r: r.get("avg") or r["base"])
        elif sort == "rating":
            results.sort(key=lambda r: -(r["rating"] or 5.0))  # BUG-04: new listings have no rating yet
        return {
            "results": results,
            "nights": len(pricing.nights(trip["check_in"], trip["check_out"])) if trip else None,
        }

    def listing_view(self, sess: dict, lid: int) -> dict:
        w = self.world(sess)
        listing = self.listing(w, lid)
        loc = data.LOCATIONS[listing["city"]]
        out = self.card(sess, listing, None)
        out |= {k: listing[k] for k in ("about", "amenities", "cleaning", "policy")}
        out |= {"host": HOSTS.get(listing["host"], "Your host"), "tax_rate": loc["tax"], "zone": loc["zone"]}
        out |= {
            "policy_text": pricing.POLICIES[listing["policy"]],
            "booked": pricing.booked_days(listing, w["bookings"]),
        }
        out["review_list"] = sorted(listing["reviews"], key=lambda r: r["date"], reverse=True)
        return out

    def trip_from(self, w: dict, src: dict) -> tuple[dict, dict]:
        listing = self.listing(w, _int(src.get("listing"), 0, 1, 10**6, "Choose a stay."))
        check_in, check_out = _date(src.get("check_in")), _date(src.get("check_out"))
        if check_out < check_in:  # BUG-06
            raise ApiError(400, "Check-out must be after check-in.")
        adults = _int(src.get("adults"), 2, 1, 16, "Choose 1 to 16 adults.")
        ages = _ages(src.get("ages"))
        pets = _int(src.get("pets"), 0, 0, 5, "Choose up to 5 pets.")
        if pets and not listing["max_pets"]:
            raise ApiError(400, "Pets aren't allowed at this stay.")
        # BUG-11: the listing's pet limit is not checked
        if pricing.occupancy(adults, ages) > listing["max_guests"]:
            raise ApiError(400, f"This stay sleeps up to {listing['max_guests']} guests.")
        # BUG-10: the minimum stay is only checked in search
        trip = {"check_in": check_in, "check_out": check_out, "adults": adults, "ages": ages, "pets": pets}
        trip["promo"] = _text(src, "promo", 30) or None
        return listing, trip

    def quote(self, sess: dict, query: dict) -> dict:
        w = self.world(sess)
        listing, trip = self.trip_from(w, {k: (query.get(k) or [""])[0] for k in query})
        try:
            return pricing.quote(listing, trip, today())
        except pricing.PriceError as err:
            raise ApiError(400, str(err)) from None

    # booking

    def hold(self, sess: dict, body: dict) -> dict:
        w, user = self.signed_in(sess, "guest")
        listing, trip = self.trip_from(w, body)
        name, email, phone = _text(body, "name", 80), _text(body, "email", 120), _text(body, "phone", 40)
        if not name or not EMAIL.fullmatch(email) or len(re.sub(r"\D", "", phone)) < 6:
            raise ApiError(400, "Check your name, email and phone number.")
        requests = body.get("requests") if isinstance(body.get("requests"), str) else ""
        if len(requests.encode()) > MAX_REQUEST_BYTES:  # BUG-20: the page allows 500 characters, not bytes
            raise ApiError(400, "Special requests can be at most 500 characters.")
        if pricing.booked_by_search(listing, w["bookings"], trip["check_in"], trip["check_out"]):
            raise ApiError(409, "Those dates were just booked. Choose other dates.")
        try:
            q = pricing.quote(listing, trip, today())
        except pricing.PriceError as err:
            raise ApiError(400, str(err)) from None
        hold_id = secrets.token_urlsafe(12)
        guest = {"name": name, "email": email, "phone": phone, "arrival": _text(body, "arrival", 20)}
        payment = "Bank transfer" if body.get("payment") == "bank" else "Pay at the property"
        w["holds"][hold_id] = {**trip, "listing": listing["id"], **guest, "requests": requests, "payment": payment}
        while len(w["holds"]) > 50:
            w["holds"].pop(next(iter(w["holds"])))
        first = pricing.deadline(listing, trip["check_in"], 1 if listing["policy"] == "flexible" else 5)
        return {"hold": hold_id, "quote": q, "policy": pricing.POLICIES[listing["policy"]]} | {
            "free_until": pricing.local(listing, first) if listing["policy"] != "strict" else None
        }

    def confirm(self, sess: dict, hold_id: str) -> dict:
        w, user = self.signed_in(sess, "guest")
        h = w["holds"].get(hold_id)  # BUG-25: the hold is never used up, so posting it again books again
        if not h:
            raise ApiError(410, "This booking session has expired.")
        listing = self.listing(w, h["listing"])
        price = pricing.charge(listing, h, today())  # PriceError for an expired code becomes a 500 (BUG-23)
        booking = {
            "ref": f"DW-{w['next_ref']}",
            "listing": listing["id"],
            "guest_id": user["id"],
            "guest_name": h["name"],
            "email": h["email"],
            "phone": h["phone"],
            "arrival": h["arrival"],
            "requests": h["requests"],
            "payment": h["payment"],
            **{k: h[k] for k in ("check_in", "check_out", "adults", "ages", "pets", "promo")},
            "status": "confirmed",
            "created": int(time.time()),
            "price": price,
        }
        w["next_ref"] += 7
        w["bookings"].append(booking)
        return booking

    # trips

    def mine(self, sess: dict, ref: str) -> tuple[dict, dict, dict]:
        w, user = self.signed_in(sess, "guest")
        b = next((b for b in w["bookings"] if b["ref"] == ref and b["guest_id"] == user["id"]), None)
        if not b:
            raise ApiError(404, "We couldn't find that trip.")
        return w, b, self.listing(w, b["listing"])

    def trip_card(self, w: dict, b: dict) -> dict:
        listing = self.listing(w, b["listing"])
        out = {k: b[k] for k in ("ref", "check_in", "check_out", "status", "adults", "ages", "pets")}
        out |= {"total": b["price"]["total"], "nights": b["price"]["nights"], "listing": listing["id"]}
        out |= {"name": listing["name"], "city": listing["city"], "image": f"/static/stay-{listing['id']}.svg"}
        return out

    def trips(self, sess: dict) -> dict:
        w, user = self.signed_in(sess, "guest")
        day = today().isoformat()
        mine = [b for b in w["bookings"] if b["guest_id"] == user["id"]]
        upcoming = [b for b in mine if b["check_in"] > day]  # BUG-26: a stay starting today is still upcoming
        past = [b for b in mine if b not in upcoming]
        return {
            "upcoming": [self.trip_card(w, b) for b in sorted(upcoming, key=lambda b: b["check_in"])],
            "past": [self.trip_card(w, b) for b in sorted(past, key=lambda b: b["check_in"], reverse=True)],
        }

    def trip(self, sess: dict, ref: str) -> dict:
        w, b, listing = self.mine(sess, ref)
        out = self.trip_card(w, b) | {"price": b["price"], "policy": listing["policy"]}
        out |= {k: b.get(k) for k in ("guest_name", "email", "phone", "arrival", "requests", "payment", "promo")}
        out |= {"policy_text": pricing.POLICIES[listing["policy"]], "zone": data.LOCATIONS[listing["city"]]["zone"]}
        out["refund"] = pricing.refund(listing, b, now()) if b["status"] == "confirmed" else None
        out["refunded"] = b.get("refunded")
        out["reviewed"] = bool(b.get("reviewed"))
        return out

    def cancel(self, sess: dict, ref: str) -> dict:
        w, b, listing = self.mine(sess, ref)
        if b["status"] != "confirmed":
            raise ApiError(400, "This trip is already cancelled.")
        r = pricing.refund(listing, b, now())
        b["status"] = "cancelled"
        b["refunded"] = r["amount"]
        return self.trip(sess, ref)

    def change(self, sess: dict, ref: str, body: dict) -> dict:
        w, b, listing = self.mine(sess, ref)
        if b["status"] != "confirmed":
            raise ApiError(400, "Cancelled trips can't be changed.")
        check_in, check_out = _date(body.get("check_in")), _date(body.get("check_out"))
        if check_out <= check_in:
            raise ApiError(400, "Check-out must be after check-in.")
        if check_in < today().isoformat():
            raise ApiError(400, "Choose dates from today on.")
        others = [x for x in w["bookings"] if x is not b]
        if pricing.booked_by_search(listing, others, check_in, check_out):
            raise ApiError(409, "Those dates aren't available.")
        b["check_in"], b["check_out"] = check_in, check_out
        b["price"]["nights"] = len(pricing.nights(check_in, check_out))  # BUG-28: the price is not recalculated
        return self.trip(sess, ref)

    def review(self, sess: dict, ref: str, body: dict) -> dict:
        w, b, listing = self.mine(sess, ref)
        # BUG-27: only stays that have ended can be reviewed
        if b.get("reviewed"):
            raise ApiError(409, "You've already reviewed this stay.")
        stars = _int(body.get("stars"), 0, 1, 5, "Choose 1 to 5 stars.")
        text = _text(body, "text", 1000)
        if len(text) < 10:
            raise ApiError(400, "Write at least 10 characters.")
        user = self.user(sess)
        listing["reviews"].append(
            {"name": user["name"].split()[0], "stars": stars, "text": text, "date": today().isoformat()}
        )
        b["reviewed"] = True
        return self.trip(sess, ref)

    # wishlist

    def wishlist(self, sess: dict) -> dict:
        w, user = self.signed_in(sess, "guest")
        cards = []
        for lid in w["wishlist"]:
            cards.append(self.card(sess, self.listing(w, lid), None))
        return {"results": cards}

    def wish(self, sess: dict, body: dict, add: bool) -> dict:
        w, user = self.signed_in(sess, "guest")
        if add:
            lid = _int(body.get("listing"), 0, 1, 10**6, "Choose a stay.")
            self.listing(w, lid)
            w["wishlist"].append(lid)
            del w["wishlist"][:-50]
        elif body.get("listing") in w["wishlist"]:  # BUG-32: the page sends the id as text
            w["wishlist"].remove(body["listing"])
        return {"saved": w["wishlist"]}

    # host

    def host(self, sess: dict) -> dict:
        w, user = self.signed_in(sess, "host")
        mine = [x for x in w["listings"] if x["host"] == user["id"]]
        ids = {x["id"] for x in mine}
        day = today()
        window = {(day + dt.timedelta(days=i)).isoformat() for i in range(30)}
        reservations, payout, taken = [], 0.0, 0
        for b in sorted(w["bookings"], key=lambda b: b["check_in"]):
            if b["listing"] not in ids or b["status"] != "confirmed":
                continue
            p = b["price"]
            amount = round(p["total"] * (1 - pricing.HOST_FEE), 2)  # BUG-38: taxes and service fee are not the host's
            start, end = pricing.d(b["check_in"]), pricing.d(b["check_out"])
            days = {(start + dt.timedelta(days=i)).isoformat() for i in range((end - start).days + 1)}  # BUG-39
            taken += len(days & window)
            if b["check_out"] >= day.isoformat():
                payout += amount
            reservations.append(
                {
                    "ref": b["ref"],
                    "listing": self.listing(w, b["listing"])["name"],
                    "guest": b["guest_name"],
                    "check_in": b["check_in"],
                    "check_out": b["check_out"],
                    "nights": p["nights"],
                    "guest_paid": p["total"],
                    "payout": amount,
                }
            )
        listings = [self.card(sess, x, None) | {"blocked": len(x["blocked"])} for x in mine]
        return {
            "listings": listings,
            "reservations": [r for r in reservations if r["check_out"] >= day.isoformat()],
            "payout": round(payout, 2),
            "occupancy": round(100 * taken / (30 * len(mine))) if mine else 0,
        }

    def host_listing(self, sess: dict, lid: int) -> dict:
        w, user = self.signed_in(sess, "host")
        listing = self.listing(w, lid)
        if listing["host"] != user["id"]:
            raise ApiError(403, "That isn't your listing.")
        keys = ("id", "name", "city", "base", "weekend", "cleaning", "min_nights", "max_guests", "blocked")
        return {k: listing[k] for k in keys}

    def save_listing(self, sess: dict, lid: int, body: dict) -> dict:
        self.host_listing(sess, lid)
        listing = self.listing(self.world(sess), lid)
        fields = {}
        for key, low, high in (("base", 1, 10000), ("weekend", 1, 10000), ("cleaning", 0, 1000)):
            value = body.get(key, listing[key])
            if isinstance(value, bool) or not isinstance(value, int | float) or not low <= value <= high:
                raise ApiError(400, f"Enter a price between {low} and {high}.")
            fields[key] = round(float(value), 2)
        fields["min_nights"] = _int(body.get("min_nights", listing["min_nights"]), 1, 0, 60, "Minimum stay: 1 to 60.")
        # BUG-37: a minimum stay of 0 nights is accepted
        fields["max_guests"] = _int(body.get("max_guests", listing["max_guests"]), 1, 1, 16, "Guests: 1 to 16.")
        blocked = body.get("blocked", listing["blocked"])
        if not isinstance(blocked, list) or len(blocked) > 366:
            raise ApiError(400, "Choose the nights to block.")
        fields["blocked"] = sorted({_date(x) for x in blocked})
        listing.update(fields)
        return self.host_listing(sess, lid)

    # accounts

    def login(self, sess: dict, body: dict) -> dict:
        w = self.world(sess)
        email = _text(body, "email").lower()
        u = next((u for u in w["users"] if u["email"] == email), None)
        password = body.get("password")
        good = isinstance(password, str) and u is not None
        if not good or not hmac.compare_digest(u["hash"], data.password_hash(password, bytes.fromhex(u["salt"]))):
            raise ApiError(401, "Incorrect email or password.")
        sess["user"] = u["id"]
        return self.me(sess)


# Server-rendered pages: the booking confirmation (after the form post) and the receipt.


def _layout(title: str, page: str, me: dict, content: str, scripts: str = "") -> bytes:
    user = me["user"]
    nav = (PAGES_DIR / "_nav-guest.html").read_text() if not user or user["role"] == "guest" else ""
    if user and user["role"] == "host":
        nav = (PAGES_DIR / "_nav-host.html").read_text()
    account = (
        f'<span class="who">{html.escape(user["name"].split()[0])}</span>'
        '<button type="button" id="logout" class="link">Log out</button>'
        if user
        else '<a href="/login" id="login-link">Log in</a>'
    )
    out = (PAGES_DIR / "_layout.html").read_text()
    values = {
        "title": html.escape(title),
        "page": page,
        "currency": me["currency"],
        "role": user["role"] if user else "",
        "nav": nav,
        "account": account,
        "content": content,
        "scripts": scripts,
    }
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", v)
    for code in CURRENCIES:
        out = out.replace(
            f'<option value="{code}">', f'<option value="{code}"{" selected" if code == me["currency"] else ""}>'
        )
    return out.encode()


def page(path: str, me: dict) -> bytes:
    name, title, _ = PAGES[path]
    script = f'<script src="/static/{name}.js" defer></script>' if (STATIC_DIR / f"{name}.js").exists() else ""
    return _layout(title, name, me, (PAGES_DIR / f"{name}.html").read_text(), script)


def confirmation_page(me: dict, booking: dict, listing: dict) -> bytes:
    p = booking["price"]
    guests = booking["adults"] + len(booking["ages"])
    body = f"""<section class="card confirm">
  <p class="eyebrow">Booking confirmed</p>
  <h1>You're going to {html.escape(listing["city"].replace("Reykjavik", "Reykjavík"))}!</h1>
  <p>Your reference is <strong id="ref">{booking["ref"]}</strong>. We've emailed the details to
    {html.escape(booking["email"])}.</p>
  <dl class="facts">
    <div><dt>Stay</dt><dd>{html.escape(listing["name"])}</dd></div>
    <div><dt>Dates</dt><dd>{booking["check_in"]} to {booking["check_out"]} ({p["nights"]} nights)</dd></div>
    <div><dt>Guests</dt><dd>{guests}</dd></div>
    <div><dt>Payment</dt><dd>{html.escape(booking["payment"])}</dd></div>
    <div class="total"><dt>Total charged</dt><dd id="charged">{money(p["total"])}</dd></div>
  </dl>
  <p class="muted small">Amounts in US dollars.</p>
  <p class="actions"><a class="btn" href="/trip?ref={booking["ref"]}">View your trip</a>
    <a class="btn btn-ghost" href="/trips">All trips</a></p>
</section>"""
    return _layout("Booking confirmed", "confirmed", me, body)


def error_page(me: dict, back: str) -> bytes:
    body = f"""<section class="card confirm">
  <h1>Something went wrong</h1>
  <p>We couldn't complete your booking. Please start again.</p>
  <p class="actions"><a class="btn" href="{html.escape(back)}">Start again</a></p>
</section>"""
    return _layout("Something went wrong", "error", me, body)


def receipt_page(me: dict, booking: dict, listing: dict) -> bytes:
    p = booking["price"]
    rate = p["tax_rate"]
    rows, taxes = [], 0.0
    for night, price in p["nightly"]:
        rows.append((f"Night of {night}", price))
        taxes += round(price * rate, 2)  # BUG-31: tax is rounded per line instead of once on the total
    if p["discount"]:
        rows.append((f"Stay discount ({round(p['discount_rate'] * 100)}%)", -p["discount"]))
        taxes -= round(p["discount"] * rate, 2)
    if p["extra"]:
        per_night = p["extra"] / p["nights"] if p["nights"] else p["extra"]
        rows.append((f"Extra guests ({p['extra_guests']})", p["extra"]))
        taxes += round(per_night * rate, 2) * (p["nights"] or 1)
    if p["pets"]:
        rows.append(("Pet fee", p["pets"]))
    rows.append(("Cleaning fee", p["cleaning"]))
    taxes += round(p["cleaning"] * rate, 2)
    rows.append(("Service fee", p["service"]))
    rows.append((f"Taxes ({rate * 100:.2f}%)", round(taxes, 2)))
    if p["promo"]:
        rows.append((f"Promo {p['promo_code']}", -p["promo"]))
    total = round(sum(v for _, v in rows), 2)
    lines = "".join(f"<tr><td>{html.escape(label)}</td><td class='num'>{money(v)}</td></tr>" for label, v in rows)
    body = f"""<section class="card receipt">
  <div class="receipt-head"><h1>Receipt</h1><span class="muted">{booking["ref"]}</span></div>
  <p><strong>{html.escape(listing["name"])}</strong>, {html.escape(listing["city"])}<br>
    {booking["check_in"]} to {booking["check_out"]} · {html.escape(booking["guest_name"])}</p>
  <table class="table"><thead><tr><th>Item</th><th class="num">Amount (USD)</th></tr></thead>
    <tbody>{lines}</tbody>
    <tfoot><tr><th>Total</th><th class="num" id="receipt-total">{money(total)}</th></tr></tfoot></table>
  <p class="muted small">Driftwood Stays (demo). This receipt is for QA testing only.</p>
  <p class="no-print"><a href="/trip?ref={booking["ref"]}">Back to your trip</a></p>
</section>"""
    return _layout(f"Receipt {booking['ref']}", "receipt", me, body)


def make_handler(store: Store | None = None):
    store = store or Store()
    static = {f.name: f for f in STATIC_DIR.iterdir() if f.is_file() and f.suffix in STATIC_TYPES}

    class Handler(BaseHTTPRequestHandler):
        server_version = "driftwood"

        def log_message(self, fmt, *args):
            pass

        def _session(self) -> tuple[str, dict, bool]:
            sid = None
            try:
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
                sid = cookie["dw_sid"].value if "dw_sid" in cookie else None
            except CookieError:
                pass
            new_sid, sess = store.session(sid)
            return new_sid, sess, new_sid != sid

        def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in {**SECURITY_HEADERS, **(extra or {})}.items():
                self.send_header(k, v)
            if self._new_sid:
                secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
                self.send_header("Set-Cookie", f"dw_sid={self._sid}; Path=/; HttpOnly; SameSite=Lax{secure}")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _html(self, status: int, body: bytes):
            self._send(status, body, "text/html; charset=utf-8")

        def _raw_body(self) -> bytes:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError(400, "Bad request.") from None
            if length > MAX_BODY:
                raise ApiError(413, "Request too large.")
            return self.rfile.read(length) if length > 0 else b""

        def _json_body(self) -> dict:
            try:
                payload = json.loads(self._raw_body() or b"{}")
            except ValueError:
                raise ApiError(400, "Send JSON.") from None
            if not isinstance(payload, dict):
                raise ApiError(400, "Send a JSON object.")
            return payload

        def do_HEAD(self):
            self._handle("GET")

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def _handle(self, method: str):
            self._sid, self._new_sid = None, False
            url = urlsplit(self.path)
            path = url.path.rstrip("/") or "/"
            query = parse_qs(url.query)
            try:
                if path == "/healthz":
                    return self._send(200, b"ok", "text/plain")
                if path == "/robots.txt":
                    return self._send(200, b"User-agent: *\nAllow: /\n", "text/plain")
                if path.startswith("/static/") and path[8:] in static:
                    f = static[path[8:]]
                    return self._send(200, f.read_bytes(), STATIC_TYPES[f.suffix])
                if path == "/api/search" and (query.get("pets") or [""])[0] == "1":
                    time.sleep(SLOW_SEARCH_SECONDS)  # BUG-05: the slow pets query can land after a newer one
                with store.lock:
                    self._sid, sess, self._new_sid = self._session()
                    if path.startswith("/api/"):
                        body = self._json_body() if method == "POST" else {}
                        return self._json(200, self._api(sess, method, path, body, query))
                    return self._page(sess, method, path, query)
            except ApiError as err:
                return self._json(err.status, {"ok": False, "error": str(err)})
            except Exception:
                return self._json(500, {"ok": False, "error": "Internal Server Error"})

        def _json(self, status: int, payload: dict):
            self._send(status, json.dumps(payload).encode(), "application/json")

        def _page(self, sess: dict, method: str, path: str, query: dict):
            me = store.me(sess)
            user = store.user(sess)
            if path == "/book/confirm" and method == "POST":
                form = parse_qs(self._raw_body().decode("utf-8", "replace"))
                hold_id = (form.get("hold") or [""])[0]
                try:
                    booking = store.confirm(sess, hold_id)
                except ApiError as err:
                    if err.status == 401:
                        return self._send(303, b"", "text/plain", {"Location": "/login?next=%2Ftrips"})
                    return self._html(err.status, error_page(me, "/search"))
                except pricing.PriceError:
                    h = store.world(sess)["holds"].get(hold_id, {})
                    back = f"/book?listing={h.get('listing', '')}&check_in={h.get('check_in', '')}"
                    back += f"&check_out={h.get('check_out', '')}"
                    return self._html(500, error_page(me, back))
                listing = store.listing(store.world(sess), booking["listing"])
                return self._html(200, confirmation_page(me, booking, listing))
            if method != "GET":
                return self._send(405, b"Method not allowed", "text/plain", {"Allow": "GET, HEAD"})
            if path == "/receipt":
                if not user:
                    return self._send(302, b"", "text/plain", {"Location": "/login?next=" + quote(self.path, safe="")})
                try:
                    w, b, listing = store.mine(sess, (query.get("ref") or [""])[0])
                except ApiError as err:
                    return self._html(404 if err.status == 404 else err.status, error_page(me, "/trips"))
                return self._html(200, receipt_page(me, b, listing))
            if path not in PAGES:
                content = (PAGES_DIR / "404.html").read_text()
                return self._html(404, _layout("Page not found", "404", me, content))
            role = PAGES[path][2]
            if role and not user:
                return self._send(302, b"", "text/plain", {"Location": "/login?next=" + quote(self.path, safe="")})
            if role and user["role"] != role:
                content = (PAGES_DIR / "403.html").read_text()
                return self._html(403, _layout("Not for this account", "403", me, content))
            return self._html(200, page(path, me))

        def _api(self, sess: dict, method: str, path: str, body: dict, query: dict):
            if method == "GET":
                gets = {
                    "/api/me": lambda: store.me(sess),
                    "/api/search": lambda: store.search(sess, query),
                    "/api/quote": lambda: store.quote(sess, query),
                    "/api/trips": lambda: store.trips(sess),
                    "/api/wishlist": lambda: store.wishlist(sess),
                    "/api/host": lambda: store.host(sess),
                }
                if path in gets:
                    return gets[path]()
                for pattern, run in (
                    (r"/api/listings/(\d+)", lambda i: store.listing_view(sess, int(i))),
                    (r"/api/trips/(DW-\d+)", lambda r: store.trip(sess, r)),
                    (r"/api/host/listings/(\d+)", lambda i: store.host_listing(sess, int(i))),
                ):
                    m = re.fullmatch(pattern, path)
                    if m:
                        return run(m.group(1))
                raise ApiError(404, "Not found.")
            posts = {
                "/api/login": lambda: store.login(sess, body),
                "/api/logout": lambda: sess.update(user=None) or {"ok": True},
                "/api/prefs": lambda: self._prefs(sess, body),
                "/api/holds": lambda: store.hold(sess, body),
                "/api/wishlist/add": lambda: store.wish(sess, body, True),
                "/api/wishlist/remove": lambda: store.wish(sess, body, False),
            }
            if path in posts:
                return posts[path]()
            for pattern, run in (
                (r"/api/trips/(DW-\d+)/cancel", lambda r: store.cancel(sess, r)),
                (r"/api/trips/(DW-\d+)/change", lambda r: store.change(sess, r, body)),
                (r"/api/trips/(DW-\d+)/review", lambda r: store.review(sess, r, body)),
                (r"/api/host/listings/(\d+)", lambda i: store.save_listing(sess, int(i), body)),
            ):
                m = re.fullmatch(pattern, path)
                if m:
                    return run(m.group(1))
            raise ApiError(404, "Not found.")

        @staticmethod
        def _prefs(sess: dict, body: dict) -> dict:
            if body.get("currency") not in CURRENCIES:
                raise ApiError(400, "Choose USD, EUR or JPY.")
            sess["currency"] = body["currency"]
            return {"currency": sess["currency"]}

    return Handler


def serve(env: dict[str, str] | None = None) -> None:
    env = dict(os.environ if env is None else env)
    port = int(env.get("PORT", "8082"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), make_handler())
    print(f"Driftwood Stays listening on :{port}", flush=True)
    httpd.serve_forever()
