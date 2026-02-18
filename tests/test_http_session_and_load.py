"""
tests/test_http_session_and_load.py
=====================================
Tests for the HTTP layer and the public load() function.
HTTP calls are mocked — no real network requests.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from imdbx._http import make_session, _ext_from_url
from imdbx import load
from imdbx.models import TitleInfo, SeriesMetadata, Episode


# ─── _ext_from_url ────────────────────────────────────────────────────────────

class TestExtFromUrl:

    def test_jpg_extension(self):
        assert _ext_from_url("https://cdn.example.com/image.jpg") == ".jpg"

    def test_jpeg_extension(self):
        assert _ext_from_url("https://cdn.example.com/image.jpeg") == ".jpeg"

    def test_png_extension(self):
        assert _ext_from_url("https://cdn.example.com/image.png") == ".png"

    def test_webp_extension(self):
        assert _ext_from_url("https://cdn.example.com/image.webp") == ".webp"

    def test_unknown_extension_defaults_to_jpg(self):
        assert _ext_from_url("https://cdn.example.com/image.bmp") == ".jpg"

    def test_no_extension_defaults_to_jpg(self):
        assert _ext_from_url("https://cdn.example.com/image") == ".jpg"

    def test_imdb_cdn_url_with_embedded_commas(self):
        """IMDBx URLs like /images/M/..._CR0,0,1000,563_.jpg 1000w must parse correctly."""
        url = "https://m.media-amazon.com/images/M/ABC_CR0,0,1000,563_.jpg"
        assert _ext_from_url(url) == ".jpg"

    def test_uppercase_extension_normalised(self):
        assert _ext_from_url("https://cdn.example.com/image.JPG") == ".jpg"


# ─── make_session ─────────────────────────────────────────────────────────────

class TestMakeSession:

    def test_returns_session(self):
        import niquests
        s = make_session()
        assert isinstance(s, niquests.Session)
        s.close()

    def test_has_user_agent_header(self):
        s = make_session()
        assert "User-Agent" in s.headers
        assert "Mozilla" in s.headers["User-Agent"]
        s.close()

    def test_pool_size_accepted(self):
        """Should not raise with various pool sizes."""
        for size in (1, 4, 16):
            s = make_session(pool_size=size)
            s.close()


# ─── load() ───────────────────────────────────────────────────────────────────

def make_json_fixture() -> dict:
    return {
        "title_id":         "tt7441658",
        "series_name":      "Black Clover",
        "type":             "TV Series",
        "years":            "2017–2021",
        "content_rating":   "TV-PG",
        "episode_duration": "24m",
        "imdb_rating":      "8.2/10",
        "rating_count":     "47K",
        "popularity":       "529",
        "tags":             ["Anime", "Action"],
        "seasons": {
            "1": [
                {
                    "episode_code":       "S1.E1",
                    "title":              "Asta and Yuno",
                    "season":             1,
                    "episode":            1,
                    "air_date":           "Tue, Oct 3, 2017",
                    "description":        "Two boys dream of greatness.",
                    "rating":             "7.6/10 (1.6K)",
                    "cover_image":        "https://m.media-amazon.com/test.jpg",
                    "cover_image_local":  None,
                    "imdb_url":           "https://www.imdbx.com/title/tt7462664/",
                }
            ]
        },
    }


class TestLoad:

    def test_returns_title_info(self, tmp_path: Path):
        p = tmp_path / "test.json"
        p.write_text(json.dumps(make_json_fixture()), encoding="utf-8")
        t = load(p)
        assert isinstance(t, TitleInfo)

    def test_meta_fields_restored(self, tmp_path: Path):
        p = tmp_path / "test.json"
        p.write_text(json.dumps(make_json_fixture()), encoding="utf-8")
        t = load(p)
        assert t.meta.title_id         == "tt7441658"
        assert t.meta.series_name      == "Black Clover"
        assert t.meta.type             == "TV Series"
        assert t.meta.years            == "2017–2021"
        assert t.meta.content_rating   == "TV-PG"
        assert t.meta.episode_duration == "24m"
        assert t.meta.imdb_rating      == "8.2/10"
        assert t.meta.rating_count     == "47K"
        assert t.meta.popularity       == "529"
        assert t.meta.tags             == ["Anime", "Action"]

    def test_seasons_restored(self, tmp_path: Path):
        p = tmp_path / "test.json"
        p.write_text(json.dumps(make_json_fixture()), encoding="utf-8")
        t = load(p)
        assert 1 in t.seasons
        assert len(t.seasons[1]) == 1

    def test_episode_fields_restored(self, tmp_path: Path):
        p = tmp_path / "test.json"
        p.write_text(json.dumps(make_json_fixture()), encoding="utf-8")
        ep = load(p).seasons[1][0]
        assert ep.episode_code == "S1.E1"
        assert ep.title        == "Asta and Yuno"
        assert ep.season       == 1
        assert ep.episode      == 1
        assert ep.rating       == "7.6/10 (1.6K)"

    def test_season_keys_are_integers(self, tmp_path: Path):
        """JSON keys are strings; load() must convert them back to int."""
        p = tmp_path / "test.json"
        p.write_text(json.dumps(make_json_fixture()), encoding="utf-8")
        t = load(p)
        assert all(isinstance(k, int) for k in t.seasons.keys())

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load("/nonexistent/path/data.json")

    def test_accepts_string_path(self, tmp_path: Path):
        p = tmp_path / "test.json"
        p.write_text(json.dumps(make_json_fixture()), encoding="utf-8")
        t = load(str(p))   # string, not Path
        assert t.meta.series_name == "Black Clover"

    def test_save_then_load_round_trip(self, tmp_path: Path):
        """Data must survive a full save → load cycle unchanged."""
        from imdbx.models import Episode, SeriesMetadata, TitleInfo

        meta = SeriesMetadata(
            title_id="tt9999999", series_name="Test Show",
            tags=["Action", "Drama"], imdb_rating="9.0/10",
        )
        ep = Episode(
            episode_code="S1.E1", title="Pilot",
            season=1, episode=1,
            air_date="Mon, Jan 1, 2024",
            description="The first episode.",
            rating="9.0/10 (5K)",
        )
        original = TitleInfo(meta=meta, seasons={1: [ep]})

        dest = tmp_path / "round_trip.json"
        original.save(dest)
        restored = load(dest)

        assert restored.meta.series_name == "Test Show"
        assert restored.meta.tags        == ["Action", "Drama"]
        assert restored.seasons[1][0].title       == "Pilot"
        assert restored.seasons[1][0].description == "The first episode."
