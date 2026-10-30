"""Driftwood's server-side planted bugs stay planted (BUGS.md) and nothing it serves gives them away."""

import datetime as dt
import http.cookiejar
import json
import re
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

import pytest

from driftwood import data, pricing, server

T = server.today()


def day(n: int) -> str:
    return (T + dt.timedelta(days=n)).isoformat()


def next_friday(after: int) -> int:
    n = after
    while (T + dt.timedelta(days=n)).weekday() != 4:
        n += 1
    return n


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, base: str):
        self.base = base
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect())

    def request(self, path: str, body=None, form: bool = False) -> tuple[int, bytes, dict]:
        if body is None:
            payload, ctype = None, "application/json"
        elif form:
            payload, ctype = urlencode(body).encode(), "application/x-www-form-urlencoded"
        else:
            payload, ctype = json.dumps(body).encode(), "application/json"
        req = urllib.request.Request(self.base + path, data=payload, headers={"Content-Type": ctype})
        try:
            with self.opener.open(req) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as err:
            return err.code, err.read(), dict(err.headers)

    def get(self, path: str, **query):
        status, raw, _ = self.request(path + ("?" + urlencode(query) if query else ""))
        return status, json.loads(raw)

    def post(self, path: str, body: dict | None = None):
        status, raw, _ = self.request(path, body or {})
        return status, json.loads(raw)

    def login(self, who: str) -> int:
        return self.post("/api/login", {"email": f"{who}@driftwood.test", "password": data.PASSWORD})[0]

    def hold(self, **trip) -> tuple[int, dict]:
        body = {"listing": 1, "adults": 2, "ages": [], "pets": 0, "name": "Gina Moreau"}
        body |= {"email": "gina@driftwood.test", "phone": "+1 555 0100"} | trip
        return self.post("/api/holds", body)


@pytest.fixture
def base_url():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(server.Store()))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture
def guest(base_url):
    c = Client(base_url)
    assert c.login("gina") == 200
    return c


@pytest.fixture
def visitor(base_url):
    return Client(base_url)


def names(result: dict) -> list[str]:
    return [r["name"] for r in result["results"]]


def test_pages_and_access(visitor):
    for path in ("/", "/search", "/listing", "/help", "/login"):
        assert visitor.request(path)[0] == 200, path
    status, _, headers = visitor.request("/trips")
    assert status == 302 and headers["Location"] == "/login?next=%2Ftrips"
    assert visitor.request("/nope")[0] == 404 and visitor.request("/healthz")[1] == b"ok"
    assert visitor.post("/api/login", {"email": "gina@driftwood.test", "password": "x"})[0] == 401
    host = Client(visitor.base)
    host.login("hal")
    assert host.request("/book")[0] == 403 and host.request("/host")[0] == 200


def test_answer_key_is_never_served_or_hinted(visitor):
    for path in ("/BUGS.md", "/static/../BUGS.md", "/server.py", "/pricing.py"):
        assert visitor.request(path)[0] == 404, path
    for folder in (server.STATIC_DIR, server.PAGES_DIR):
        for f in folder.iterdir():
            assert not re.search(r"bug|planted", f.read_text(), re.I), f.name


def test_search_bugs(visitor):
    s = visitor.get("/api/search", location="Honolulu", check_in=day(9), check_out=day(14))[1]
    assert "Lanikai Beach Cottage" in names(s)  # BUG-01: booked day 10 to 13
    assert "Shibuya Sky Apartment" in names(visitor.get("/api/search", location="Tokyo", ages="8,10")[1])  # BUG-02
    fri = next_friday(28)
    s = visitor.get("/api/search", location="Honolulu", check_in=day(fri), check_out=day(fri + 2), max_price=200)[1]
    lanikai = next(r for r in s["results"] if r["id"] == 1)
    assert lanikai["avg"] > 200  # BUG-03
    assert visitor.get("/api/search", sort="rating")[1]["results"][0]["rating"] is None  # BUG-04


def test_pricing_rules():
    lanikai = {**data.LISTINGS[0], "blocked": []}
    fri = next_friday(28)
    trip = {"check_in": day(fri), "check_out": day(fri + 2), "adults": 2, "ages": [], "pets": 0}
    assert pricing.quote(lanikai, trip, T)["weekend_nights"] == 1  # BUG-12: Friday and Saturday are both weekend
    seven = pricing.quote(lanikai, trip | {"check_out": day(fri + 7)}, T)
    eight = pricing.quote(lanikai, trip | {"check_out": day(fri + 8)}, T)
    assert seven["discount"] == 0 and eight["discount_rate"] == 0.10  # BUG-13
    assert eight["service"] == round(0.12 * eight["subtotal"], 2)  # BUG-14
    q, c = pricing.quote(lanikai, trip, T), pricing.charge(lanikai, trip, T)
    assert abs(c["tax"] - q["tax"] - 90 * 0.1396) <= 0.011  # BUG-15: cleaning taxed only when charged
    assert pricing.quote(lanikai, trip | {"ages": [12]}, T)["extra_guests"] == 1  # BUG-16
    three = trip | {"adults": 3, "check_out": day(fri + 3)}
    assert (
        pricing.quote(lanikai, three, T)["extra"] == 25 and pricing.charge(lanikai, three, T)["extra"] == 75
    )  # BUG-21
    promo = pricing.quote(lanikai, three | {"promo": "stay15"}, T)
    before = pricing.quote(lanikai, three, T)["total"]
    assert promo["promo"] == round(before * 0.15, 2)  # BUG-24
    assert pricing.quote(lanikai, trip | {"promo": "SUMMER25"}, T)["promo"] > 0  # BUG-23: expiry not checked
    with pytest.raises(pricing.PriceError):
        pricing.charge(lanikai, trip | {"promo": "SUMMER25"}, T)


def test_listing_rules(guest):
    booked = guest.get("/api/listings/1")[1]["booked"]
    assert day(13) in booked  # BUG-08: Ravi checks out that day
    status, h = guest.hold(check_in=day(40), check_out=day(41))
    assert status == 200 and h["quote"]["nights"] == 1  # BUG-10: Lanikai's minimum is 2 nights
    assert guest.hold(listing=7, check_in=day(40), check_out=day(42), pets=2)[0] == 200  # BUG-11: 1 pet max
    assert guest.hold(listing=2, check_in=day(40), check_out=day(40))[1]["quote"]["nights"] == 0  # BUG-06
    assert guest.hold(listing=2, check_in=day(40), check_out=day(39))[0] == 400
    assert guest.hold(check_in=day(60), check_out=day(62), requests="é" * 300)[0] == 400  # BUG-20
    assert guest.hold(check_in=day(60), check_out=day(62), requests="e" * 500)[0] == 200


def test_confirm_can_be_posted_twice(guest):  # BUG-25
    status, h = guest.hold(check_in=day(70), check_out=day(73))
    first = guest.request("/book/confirm", {"hold": h["hold"]}, form=True)
    second = guest.request("/book/confirm", {"hold": h["hold"]}, form=True)
    assert first[0] == second[0] == 200
    refs = [re.search(rb'id="ref">(DW-\d+)<', page[1]).group(1) for page in (first, second)]
    assert refs[0] != refs[1]
    expired = guest.hold(check_in=day(80), check_out=day(82), promo="SUMMER25")[1]
    assert guest.request("/book/confirm", {"hold": expired["hold"]}, form=True)[0] == 500  # BUG-23


def test_trips(guest):
    trips = guest.get("/api/trips")[1]
    assert any(t["check_in"] == day(0) for t in trips["past"])  # BUG-26
    shibuya = guest.get("/api/trips/DW-4721")[1]
    assert "12:00 AM (Tokyo time)" in shibuya["refund"]["until"]  # BUG-29
    assert guest.post("/api/trips/DW-4721/review", {"stars": 5, "text": "Before we even went!"})[0] == 200  # BUG-27
    flat = guest.get("/api/trips/DW-4795")[1]
    assert flat["refund"]["amount"] == flat["price"]["total"]  # BUG-30: includes the service fee
    changed = guest.post("/api/trips/DW-4795/change", {"check_in": day(20), "check_out": day(27)})[1]
    assert changed["nights"] == 7 and changed["total"] == flat["total"]  # BUG-28
    guest.post("/api/trips/DW-4795/cancel")
    s = guest.get("/api/search", location="Reykjavik", check_in=day(21), check_out=day(23))[1]
    assert "Harbour View Flat" not in names(s)  # BUG-33
    receipts = []
    for ref in ("DW-4721", "DW-4758"):
        page = guest.request(f"/receipt?ref={ref}")[1].decode()
        receipts.append(re.search(r'id="receipt-total">\$([\d,.]+)<', page).group(1).replace(",", ""))
    totals = [str(guest.get(f"/api/trips/{ref}")[1]["total"]) for ref in ("DW-4721", "DW-4758")]
    assert receipts != totals  # BUG-31 (rounding depends on the nights, so one of them differs)


def test_wishlist(guest):  # BUG-32
    guest.post("/api/wishlist/add", {"listing": "3"})
    guest.post("/api/wishlist/remove", {"listing": "3"})
    guest.post("/api/wishlist/add", {"listing": "3"})
    assert names(guest.get("/api/wishlist")[1]) == ["North Shore Surf House"] * 2


def test_host(base_url):
    host = Client(base_url)
    host.login("hal")
    h = host.get("/api/host")[1]
    r = h["reservations"][0]
    assert r["payout"] == round(r["guest_paid"] * 0.97, 2)  # BUG-38
    booked = 0
    for x in h["reservations"]:
        start, end = dt.date.fromisoformat(x["check_in"]), dt.date.fromisoformat(x["check_out"])
        booked += sum(1 for i in range((end - start).days) if 0 <= ((start + dt.timedelta(days=i)) - T).days < 30)
    assert h["occupancy"] > round(100 * booked / 90)  # BUG-39
    listing = host.get("/api/host/listings/1")[1]
    assert host.post("/api/host/listings/1", listing | {"min_nights": 0})[1]["min_nights"] == 0  # BUG-37
    assert host.post("/api/host/listings/1", listing | {"base": 0})[0] == 400
    assert host.get("/api/host/listings/2")[0] == 403


def test_bad_requests(guest):
    assert guest.get("/api/listings/999")[0] == 404
    assert guest.get("/api/trips/DW-1")[0] == 404
    assert guest.get("/api/quote", listing=1, check_in="nope", check_out=day(3))[0] == 400
    assert guest.hold(check_in=day(40), check_out=day(42), adults=5)[0] == 400
