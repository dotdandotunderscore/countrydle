import random
from collections import Counter

import pytest

from wheredle.sourcing import candidates
from wheredle.sourcing.commons import _clean, _pick_coord


def _candidate(**overrides):
    base = {
        "title": "File:Beautiful fjord.jpg",
        "pageid": 123,
        "mime": "image/jpeg",
        "width": 4000,
        "height": 3000,
        "lat": 60.0,
        "lon": 5.0,
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def fake_geocode(monkeypatch):
    # Avoid the offline reverse-geocoder dataset in unit tests; pretend everything is Norway.
    monkeypatch.setattr(candidates, "country_for", lambda lat, lon: "NO")


def test_qualify_accepts_good_candidate():
    assert candidates.qualify(_candidate()) == "NO"


def test_qualify_rejects_small_image():
    assert candidates.qualify(_candidate(width=800, height=600)) is None


def test_qualify_rejects_wrong_mime():
    assert candidates.qualify(_candidate(mime="image/svg+xml")) is None


def test_qualify_rejects_blocked_title():
    assert candidates.qualify(_candidate(title="File:Map of Norway.jpg")) is None


def test_clean_strips_html():
    assert _clean('<a href="x">Jane Doe</a>') == "Jane Doe"
    assert _clean(None) is None


def test_pick_coord_prefers_object_location():
    coords = [
        {"lat": 1.0, "lon": 1.0, "primary": "", "globe": "earth"},  # camera (primary)
        {"lat": 2.0, "lon": 2.0, "globe": "earth"},                  # object (secondary)
    ]
    assert _pick_coord(coords) == {"lat": 2.0, "lon": 2.0}


def test_load_categories_returns_iso2_category_pairs():
    catalogue = candidates._load_categories()
    assert catalogue
    assert all(len(iso2) == 2 and category for iso2, category in catalogue)


def test_gather_caps_contribution_per_country(monkeypatch):
    random.seed(0)
    pool = [_candidate(pageid=i, author=f"a{i}") for i in range(20)]
    monkeypatch.setattr(candidates, "fetch_candidates", lambda category, limit=60: list(pool))

    out = candidates.gather(per_country=5, countries_per_run=1, catalogue=[("NO", "no")])

    assert len(out) == 5


def test_gather_balances_across_countries(monkeypatch):
    random.seed(0)

    def fake_fetch(category, limit=60):
        return [_candidate(pageid=f"{category}{i}", author=f"{category}{i}", cat=category) for i in range(10)]

    monkeypatch.setattr(candidates, "fetch_candidates", fake_fetch)
    catalogue = [("NO", "no"), ("JP", "jp"), ("KE", "ke")]

    out = candidates.gather(per_country=3, countries_per_run=3, catalogue=catalogue)

    counts = Counter(candidate["cat"] for candidate, _ in out)
    assert counts == {"no": 3, "jp": 3, "ke": 3}


def test_gather_dedups_shared_author(monkeypatch):
    random.seed(0)
    pool = [_candidate(pageid=i, author="same hand") for i in range(5)]
    monkeypatch.setattr(candidates, "fetch_candidates", lambda category, limit=60: list(pool))

    out = candidates.gather(per_country=5, countries_per_run=1, catalogue=[("NO", "no")])

    assert len(out) == 1
