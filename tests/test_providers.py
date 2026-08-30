import pytest
from unittest.mock import MagicMock
from kira.providers import OnlineMangaProvider


def _make_response(payload, status_code=200):
    res = MagicMock()
    res.status_code = status_code
    res.json.return_value = payload
    return res


ANILIST_PAYLOAD = {
    "data": {
        "Media": {
            "id": 232,
            "title": {"english": "Monster", "romaji": "Monster", "native": "モンスター"},
            "volumes": 18,
            "chapters": 162,
            "description": "A masterpiece. (asHtml false)",
            "coverImage": {"extraLarge": "https://img.example/monster.jpg", "large": "https://img.example/monster.jpg"},
            "staff": {
                "edges": [
                    {"role": "Story & Art", "node": {"name": {"full": "Naoki Urasawa"}}},
                ]
            },
        }
    }
}


def test_search_manga_metadata_success(monkeypatch):
    monkeypatch.setattr(
        OnlineMangaProvider,
        "_request_with_retry",
        classmethod(lambda cls, *args, **kwargs: _make_response(ANILIST_PAYLOAD)),
    )
    meta = OnlineMangaProvider.search_manga_metadata("Monster")
    assert meta is not None
    assert meta["title"] == "Monster"
    assert "Urasawa" in meta["author"]
    assert meta["cover_url"] is not None


def test_search_manga_metadata_jikan_fallback(monkeypatch):
    # AniList returns None (failed request), Jikan responds
    def fake_request(cls, method, url, **kwargs):
        if OnlineMangaProvider.ANILIST_URL in url:
            return None
        return _make_response({
            "data": [
                {
                    "mal_id": 19,
                    "title": "Monster",
                    "title_english": "Monster",
                    "synopsis": "A masterpiece.",
                    "volumes": 18,
                    "chapters": 162,
                    "images": {"jpg": {"large_image_url": "https://img.example/monster.jpg"}},
                    "authors": [{"name": "Naoki Urasawa"}],
                }
            ]
        })

    monkeypatch.setattr(OnlineMangaProvider, "_request_with_retry", classmethod(fake_request))
    meta = OnlineMangaProvider.search_manga_metadata("Monster")
    assert meta is not None
    assert meta["title"] == "Monster"
    assert "Urasawa" in meta["author"]


def test_search_manga_metadata_anilist_error_status(monkeypatch):
    # AniList returns 429 (rate-limit), Jikan also fails -> None
    def fake_request(cls, method, url, **kwargs):
        if OnlineMangaProvider.ANILIST_URL in url:
            return _make_response({}, status_code=429)
        return _make_response({}, status_code=500)

    monkeypatch.setattr(OnlineMangaProvider, "_request_with_retry", classmethod(fake_request))
    assert OnlineMangaProvider.search_manga_metadata("Monster") is None


def _mangadex_search_payload():
    return {
        "data": [
            {"id": "manga_123", "attributes": {}},
        ]
    }


def test_fetch_volume_chapter_mapping_success(monkeypatch):
    def fake_request(cls, method, url, **kwargs):
        if "/manga" in url and "/aggregate" not in url:
            return _make_response(_mangadex_search_payload())
        if url.endswith("/aggregate"):
            return _make_response({
                "volumes": {
                    "1": {"chapters": {"1": {}, "2": {}, "3": {}}},
                    "2": {"chapters": {"1": {"publishDate": "2020-01-01"}, "2": {}}},
                }
            })
        return _make_response({}, status_code=404)

    monkeypatch.setattr(OnlineMangaProvider, "_request_with_retry", classmethod(fake_request))
    mapping = OnlineMangaProvider.fetch_volume_chapter_mapping("Fullmetal Alchemist")
    assert mapping is not None
    assert mapping == {1: [1, 2, 3], 2: [1, 2]}


def test_fetch_volume_chapter_mapping_returns_none_on_failure(monkeypatch):
    monkeypatch.setattr(
        OnlineMangaProvider,
        "_request_with_retry",
        classmethod(lambda cls, *args, **kwargs: None),
    )
    assert OnlineMangaProvider.fetch_volume_chapter_mapping("Fullmetal Alchemist") is None


def test_fetch_volume_covers_parses_mangadex(monkeypatch):
    def fake_request(cls, method, url, **kwargs):
        if url.endswith("/manga"):
            return _make_response(_mangadex_search_payload())
        if url.endswith("/cover"):
            return _make_response({
                "data": [
                    {"attributes": {"volume": "1", "fileName": "cover1.jpg"}},
                    {"attributes": {"volume": "2", "fileName": "cover2.jpg"}},
                    {"attributes": {"volume": None, "fileName": "coverNone.jpg"}},
                ]
            })
        return _make_response({}, status_code=404)

    monkeypatch.setattr(OnlineMangaProvider, "_request_with_retry", classmethod(fake_request))
    covers = OnlineMangaProvider.fetch_volume_covers("Fullmetal Alchemist")
    assert covers == {
        1: "https://uploads.mangadex.org/covers/manga_123/cover1.jpg",
        2: "https://uploads.mangadex.org/covers/manga_123/cover2.jpg",
    }


def test_retry_handles_rate_limit_and_recovers(monkeypatch):
    calls = {"n": 0}

    def fake_request_request(method, url, **kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            res = MagicMock()
            res.status_code = 429
            return res
        res = MagicMock()
        res.status_code = 200
        res.json.return_value = ANILIST_PAYLOAD
        return res

    monkeypatch.setattr("kira.providers.requests.request", fake_request_request)
    monkeypatch.setattr("kira.providers.time.sleep", lambda *a, **k: None)

    res = OnlineMangaProvider._request_with_retry("POST", "$FAKE_URL$")
    assert res is not None
    assert calls["n"] == 2


def test_retry_returns_none_on_persistent_5xx(monkeypatch):
    def fake_request_request(method, url, **kwargs):
        res = MagicMock()
        res.status_code = 503
        return res

    monkeypatch.setattr("kira.providers.requests.request", fake_request_request)
    monkeypatch.setattr("kira.providers.time.sleep", lambda *a, **k: None)

    assert OnlineMangaProvider._request_with_retry("GET", "$FAKE_URL$") is None


def test_retry_returns_none_on_connection_error(monkeypatch):
    import requests as req

    def fake_request_request(method, url, **kwargs):
        raise req.RequestException("Connection refused")

    monkeypatch.setattr("kira.providers.requests.request", fake_request_request)
    monkeypatch.setattr("kira.providers.time.sleep", lambda *a, **k: None)

    assert OnlineMangaProvider._request_with_retry("GET", "$FAKE_URL$") is None
