"""
/api/directions language support (v1.5 Phase 2).

Covers:
  • cache key changes per language, so en/es/fr/zh-Hans requests for the same
    route never collide
  • unsupported/missing language codes normalize to English before touching
    the cache or Google
  • app locale codes map to Google's `language` param (zh-Hans → zh-CN)
  • the English-only instruction cleanup (_clean_instruction/_extract_steps)
    is skipped for non-English responses rather than run as a silent no-op
  • fetch_directions forwards `language` to Google and caches per language

No network — httpx.Client and Redis are both faked.
"""

import pytest

from app.routers import directions as directions_mod
from app.routers.directions import (
    DirectionsError,
    _cache_key,
    _clean_instruction,
    _extract_steps,
    _normalize_language,
    fetch_directions,
)

ORIGIN = "34.05,-118.25"
DEST = "34.02,-118.29"


# ── Pure helpers ────────────────────────────────────────────────────────────

def test_normalize_language_passes_through_supported_codes():
    assert _normalize_language("es") == "es"
    assert _normalize_language("fr") == "fr"
    assert _normalize_language("zh-Hans") == "zh-Hans"
    assert _normalize_language("en") == "en"


def test_normalize_language_falls_back_to_english():
    assert _normalize_language(None) == "en"
    assert _normalize_language("") == "en"
    assert _normalize_language("de") == "en"  # not one of our 4 supported languages


def test_google_language_maps_zh_hans_to_zh_cn():
    from app.routers.directions import _GOOGLE_LANGUAGE

    assert _GOOGLE_LANGUAGE["zh-Hans"] == "zh-CN"
    assert _GOOGLE_LANGUAGE["en"] == "en"
    assert _GOOGLE_LANGUAGE["es"] == "es"
    assert _GOOGLE_LANGUAGE["fr"] == "fr"


def test_cache_key_differs_by_language_only():
    en_key = _cache_key(ORIGIN, DEST, "transit", "en")
    es_key = _cache_key(ORIGIN, DEST, "transit", "es")
    zh_key = _cache_key(ORIGIN, DEST, "transit", "zh-Hans")
    assert len({en_key, es_key, zh_key}) == 3


def test_cache_key_stable_for_same_inputs():
    assert _cache_key(ORIGIN, DEST, "transit", "es") == _cache_key(ORIGIN, DEST, "transit", "es")


def test_clean_instruction_applies_only_to_english():
    en = _clean_instruction("Head northwest on Main St toward Elm St", "", "en")
    assert en == "Continue on Main St"

    # Spanish text superficially containing "toward"-adjacent words must NOT
    # be mangled by the English-only regexes — clean_instruction should just
    # strip whitespace and return it untouched.
    es_raw = "Dirígete al noroeste por Main St hacia Elm St"
    assert _clean_instruction(es_raw, "", "es") == es_raw


def test_extract_steps_skips_admin_note_stripping_for_non_english():
    leg = {
        "steps": [
            {
                "html_instructions": "Turn left onto Elm St Restricted usage road",
                "travel_mode": "WALKING",
                "distance": {"value": 10},
                "duration": {"value": 5},
                "polyline": {"points": "p1"},
            },
        ],
    }
    en_steps = _extract_steps(leg, "en")
    assert en_steps[0]["instruction"] == "Turn left onto Elm St"

    fr_steps = _extract_steps(leg, "fr")
    # French responses keep whatever Google actually sent — the English
    # "Restricted usage road" filter must not fire on non-English text.
    assert "Restricted usage road" in fr_steps[0]["instruction"]


# ── fetch_directions: cache + Google param wiring ───────────────────────────

class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.set_calls = 0

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, val):
        self.set_calls += 1
        self.store[key] = val


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeHttpxClient:
    """Records every GET's params; returns a canned OK Directions payload."""

    calls: list[dict] = []

    def __init__(self, timeout=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, params=None):
        FakeHttpxClient.calls.append(params)
        return FakeResponse({
            "status": "OK",
            "routes": [{
                "overview_polyline": {"points": "poly"},
                "legs": [{
                    "distance": {"value": 1000},
                    "duration": {"value": 600},
                    "steps": [],
                }],
            }],
        })


@pytest.fixture
def fake_backends(monkeypatch):
    fake_redis = FakeRedis()
    FakeHttpxClient.calls = []
    monkeypatch.setattr(directions_mod, "get_redis", lambda: fake_redis)
    monkeypatch.setattr(directions_mod.httpx, "Client", FakeHttpxClient)
    monkeypatch.setattr(directions_mod, "_api_key", lambda: "TEST_KEY")
    return fake_redis


def test_fetch_directions_sends_googles_mapped_language(fake_backends):
    fetch_directions(ORIGIN, DEST, "walking", language="zh-Hans")
    assert FakeHttpxClient.calls[-1]["language"] == "zh-CN"


def test_fetch_directions_defaults_unsupported_language_to_english(fake_backends):
    fetch_directions(ORIGIN, DEST, "walking", language="klingon")
    assert FakeHttpxClient.calls[-1]["language"] == "en"


def test_fetch_directions_caches_separately_per_language(fake_backends):
    fetch_directions(ORIGIN, DEST, "walking", language="en")
    fetch_directions(ORIGIN, DEST, "walking", language="es")
    # Two distinct cache entries were written — no collision between languages.
    assert fake_backends.set_calls == 2
    assert len(fake_backends.store) == 2


def test_fetch_directions_second_call_same_language_hits_cache(fake_backends):
    fetch_directions(ORIGIN, DEST, "walking", language="fr")
    calls_after_first = len(FakeHttpxClient.calls)
    fetch_directions(ORIGIN, DEST, "walking", language="fr")
    assert len(FakeHttpxClient.calls) == calls_after_first  # no second Google call
    assert fake_backends.set_calls == 1


def test_fetch_directions_missing_key_raises_500(monkeypatch):
    monkeypatch.setattr(directions_mod, "_api_key", lambda: None)
    with pytest.raises(DirectionsError) as exc_info:
        fetch_directions(ORIGIN, DEST, "walking", language="en")
    assert exc_info.value.status_code == 500
