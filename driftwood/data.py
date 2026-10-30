"""Driftwood Stays' demo world: listings, reviews, accounts and bookings, dated from today.

Every visitor gets a fresh copy (see server.Store), so scans never disturb each other.
"""

import datetime as dt
import hashlib

PASSWORD = "Driftwood@2026"
SALT = b"driftwood-demo-salt"

# Locations keep a fixed UTC offset (none of them observes daylight saving time).
LOCATIONS = {
    "Honolulu": {"country": "United States", "offset": -10, "zone": "Honolulu time", "tax": 0.1396},
    "Tokyo": {"country": "Japan", "offset": 9, "zone": "Tokyo time", "tax": 0.1035},
    "Reykjavik": {"country": "Iceland", "offset": 0, "zone": "Reykjavík time", "tax": 0.115},
}

USERS = [
    {"id": 1, "name": "Gina Moreau", "email": "gina@driftwood.test", "role": "guest"},
    {"id": 2, "name": "Hal Okafor", "email": "hal@driftwood.test", "role": "host"},
]

# fmt: off
LISTINGS = [
    {"id": 1, "name": "Lanikai Beach Cottage", "city": "Honolulu", "type": "House", "base": 180, "weekend": 240,
     "cleaning": 90, "max_guests": 4, "max_pets": 1, "min_nights": 2, "policy": "moderate", "host": 2,
     "amenities": ["Wi-Fi", "Kitchen", "Free parking", "Beach access", "Washer"],
     "about": "A breezy two-bedroom cottage a short walk from Lanikai Beach, with an outdoor shower and a lanai."},
    {"id": 2, "name": "Diamond Head Studio", "city": "Honolulu", "type": "Apartment", "base": 120, "weekend": 150,
     "cleaning": 50, "max_guests": 2, "max_pets": 0, "min_nights": 1, "policy": "flexible", "host": 3,
     "amenities": ["Wi-Fi", "Kitchenette", "Air conditioning", "Pool"],
     "about": "A bright studio with a view of Diamond Head, ten minutes from Waikīkī by bus."},
    {"id": 3, "name": "North Shore Surf House", "city": "Honolulu", "type": "House", "base": 260, "weekend": 320,
     "cleaning": 120, "max_guests": 8, "max_pets": 2, "min_nights": 3, "policy": "strict", "host": 3,
     "amenities": ["Wi-Fi", "Kitchen", "Free parking", "Surfboard rack", "Hot tub"],
     "about": "Four bedrooms across from Sunset Beach, with a big kitchen and room for the whole crew."},
    {"id": 4, "name": "Shibuya Sky Apartment", "city": "Tokyo", "type": "Apartment", "base": 150, "weekend": 190,
     "cleaning": 60, "max_guests": 3, "max_pets": 0, "min_nights": 1, "policy": "flexible", "host": 2,
     "amenities": ["Wi-Fi", "Kitchen", "Washer", "Air conditioning", "City view"],
     "about": "A 22nd-floor apartment above Shibuya, five minutes on foot from the station."},
    {"id": 5, "name": "Asakusa Machiya House", "city": "Tokyo", "type": "House", "base": 210, "weekend": 280,
     "cleaning": 80, "max_guests": 5, "max_pets": 0, "min_nights": 2, "policy": "moderate", "host": 3,
     "amenities": ["Wi-Fi", "Kitchen", "Tatami room", "Garden"],
     "about": "A restored wooden townhouse near Sensō-ji, with tatami rooms and a tiny garden."},
    {"id": 6, "name": "Ginza Capsule Loft", "city": "Tokyo", "type": "Room", "base": 70, "weekend": 95,
     "cleaning": 20, "max_guests": 1, "max_pets": 0, "min_nights": 1, "policy": "flexible", "host": 3,
     "amenities": ["Wi-Fi", "Shared lounge", "Luggage storage"],
     "about": "A quiet sleeping loft in the heart of Ginza for solo travellers."},
    {"id": 7, "name": "Harbour View Flat", "city": "Reykjavik", "type": "Apartment", "base": 140, "weekend": 175,
     "cleaning": 55, "max_guests": 3, "max_pets": 1, "min_nights": 2, "policy": "moderate", "host": 2,
     "amenities": ["Wi-Fi", "Kitchen", "Washer", "Harbour view"],
     "about": "A top-floor flat over the old harbour, a short walk from Harpa and the main street."},
    {"id": 8, "name": "Aurora Glass Cabin", "city": "Reykjavik", "type": "Cabin", "base": 230, "weekend": 300,
     "cleaning": 100, "max_guests": 4, "max_pets": 0, "min_nights": 2, "policy": "strict", "host": 3,
     "amenities": ["Wi-Fi", "Hot tub", "Free parking", "Glass roof"],
     "about": "A glass-roofed cabin 40 minutes from town, made for watching the northern lights from bed."},
    {"id": 9, "name": "Lava Field Guest Room", "city": "Reykjavik", "type": "Room", "base": 95, "weekend": 115,
     "cleaning": 30, "max_guests": 2, "max_pets": 0, "min_nights": 1, "policy": "flexible", "host": 3,
     "amenities": ["Wi-Fi", "Breakfast", "Free parking"],
     "about": "A private room in a family home at the edge of a moss-covered lava field."},
]

REVIEWS = {  # listing: (name, stars, text, days ago)
    1: [("Ana", 5, "Exactly as pictured, and the beach is magic at sunrise.", 20),
        ("Ben", 5, "Spotless, and Hal's tips were great.", 45), ("Chloé", 5, "We didn't want to leave.", 70),
        ("Dev", 5, "Perfect for a family of four.", 95), ("Eli", 5, "Lovely lanai, comfy beds.", 130),
        ("Fumi", 4, "Great spot; parking is tight.", 160), ("Gus", 5, "Would book again tomorrow.", 200)],
    2: [("Hana", 5, "Great value and a lovely pool.", 30), ("Ivo", 4, "Small but well thought out.", 60),
        ("Jay", 4, "Bus stop right outside.", 110), ("Kim", 5, "Sunsets from the balcony!", 150)],
    3: [("Lea", 5, "Room for all eight of us.", 25), ("Max", 4, "Loud road, amazing beach.", 90),
        ("Nia", 5, "Best surf trip ever.", 140)],
    4: [("Oto", 5, "The view at night is unreal.", 12), ("Pia", 5, "Spotless and so central.", 50),
        ("Quin", 5, "Easy check-in, great host.", 80), ("Ray", 5, "Everything we needed.", 120),
        ("Sol", 4, "A little noisy on Friday night.", 170)],
    5: [("Taro", 4, "Beautiful house, steep stairs.", 40), ("Uma", 5, "Felt like old Tokyo.", 100)],
    7: [("Vik", 5, "Harbour view from the bed!", 15), ("Wen", 4, "Cosy and warm.", 75),
        ("Xan", 4, "Great location.", 130)],
    8: [("Yara", 5, "We saw the aurora on night two.", 35), ("Zed", 5, "Unforgettable.", 85),
        ("Abe", 4, "Bring snacks: it's remote.", 160)],
}

# Bookings: listing, guest (user id, or a name for someone else), check-in (days from today), nights,
# adults, children's ages, pets
BOOKINGS = [
    (4, 1, 3, 3, 2, [], 0),      # Gina, Tokyo, flexible: upcoming
    (1, 1, 0, 4, 2, [], 0),      # Gina, checks in today
    (7, 1, 20, 5, 2, [], 0),     # Gina, Reykjavík, moderate: upcoming
    (8, 1, -40, 4, 2, [], 0),    # Gina, past stay
    (2, 1, -90, 3, 2, [], 0),    # Gina, past stay
    (1, "Ravi Shah", 10, 3, 2, [7], 0),
    (7, "Mia Jensen", 8, 2, 1, [], 0),
    (4, "Kenji Ito", 12, 4, 2, [], 0),
    (8, "Lena Vogel", 5, 4, 2, [], 0),
    (4, "Omar Haddad", -6, 2, 2, [], 0),
    (1, "Sara Lind", -12, 5, 3, [], 1),
]
# fmt: on


def password_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 20_000).hex()


DEMO_HASH = password_hash(PASSWORD, SALT)


def world(today: dt.date, now: float) -> dict:
    """A fresh copy of everything one visitor can see and change. Booking prices are filled in by the server."""

    def day(offset: int) -> str:
        return (today + dt.timedelta(days=offset)).isoformat()

    listings = []
    for spec in LISTINGS:
        listing = {**spec, "amenities": list(spec["amenities"]), "blocked": []}
        listing["reviews"] = [
            {"name": n, "stars": s, "text": t, "date": day(-ago)} for n, s, t, ago in REVIEWS.get(spec["id"], [])
        ]
        listings.append(listing)
    users = [{**u, "salt": SALT.hex(), "hash": DEMO_HASH} for u in USERS]
    bookings = []
    for i, (lid, guest, start, nights, adults, ages, pets) in enumerate(BOOKINGS):
        mine = guest == 1
        bookings.append(
            {
                "ref": f"DW-{4721 + i * 37}",
                "listing": lid,
                "guest_id": 1 if mine else None,
                "guest_name": "Gina Moreau" if mine else guest,
                "email": "gina@driftwood.test" if mine else "guest@example.com",
                "check_in": day(start),
                "check_out": day(start + nights),
                "adults": adults,
                "ages": list(ages),
                "pets": pets,
                "promo": None,
                "status": "confirmed",
                "created": int(now - (abs(start) + 20) * 86400),
            }
        )
    return {"listings": listings, "users": users, "bookings": bookings, "wishlist": [], "holds": {}, "next_ref": 9100}
