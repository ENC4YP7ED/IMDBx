"""
tests/test_models_episode_dataclass.py
=======================================
Unit tests for the Episode dataclass.
No network, no browser — pure in-memory.
"""

import pytest
from imdbx.models import Episode


def make_episode(**kwargs) -> Episode:
    defaults = dict(
        episode_code      = "S1.E1",
        title             = "Asta and Yuno",
        season            = 1,
        episode           = 1,
        air_date          = "Tue, Oct 3, 2017",
        description       = "Two young boys raised together dream of becoming the Wizard King.",
        rating            = "7.6/10 (1.6K)",
        cover_image       = "https://m.media-amazon.com/images/test.jpg",
        cover_image_local = None,
        imdb_url          = "https://www.imdb.com/title/tt7462664/",
    )
    defaults.update(kwargs)
    return Episode(**defaults)


class TestEpisodeCreation:

    def test_all_fields_stored(self):
        ep = make_episode()
        assert ep.episode_code == "S1.E1"
        assert ep.title        == "Asta and Yuno"
        assert ep.season       == 1
        assert ep.episode      == 1
        assert ep.rating       == "7.6/10 (1.6K)"

    def test_optional_fields_default_none(self):
        ep = make_episode(cover_image=None, cover_image_local=None)
        assert ep.cover_image       is None
        assert ep.cover_image_local is None

    def test_imdb_url_defaults_empty_string(self):
        ep = make_episode(imdb_url="")
        assert ep.imdb_url == ""

    def test_str_representation(self):
        ep = make_episode()
        s  = str(ep)
        assert "S1.E1"         in s
        assert "Asta and Yuno" in s
        assert "7.6/10"        in s

    def test_to_dict_is_serialisable(self):
        import json
        ep = make_episode()
        d  = ep.to_dict()
        assert isinstance(d, dict)
        # Must be JSON-serialisable without errors
        json.dumps(d)
        assert d["episode_code"] == "S1.E1"
        assert d["season"]       == 1

    def test_to_dict_has_all_keys(self):
        ep   = make_episode()
        keys = ep.to_dict().keys()
        for field in ("episode_code", "title", "season", "episode",
                      "air_date", "description", "rating",
                      "cover_image", "cover_image_local", "imdb_url"):
            assert field in keys


class TestEpisodeEdgeCases:

    def test_empty_strings_allowed(self):
        ep = make_episode(air_date="", description="", rating="N/A")
        assert ep.air_date    == ""
        assert ep.description == ""
        assert ep.rating      == "N/A"

    def test_unicode_title(self):
        ep = make_episode(title="Shōnen Hero: 少年")
        assert ep.title == "Shōnen Hero: 少年"

    def test_season_zero_allowed(self):
        """Season 0 is used for specials on IMDBx."""
        ep = make_episode(season=0, episode=1, episode_code="S0.E1")
        assert ep.season == 0
