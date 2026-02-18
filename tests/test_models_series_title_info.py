"""
tests/test_models_series_title_info.py
=======================================
Unit tests for SeriesMetadata and TitleInfo dataclasses.
No network, no browser — pure in-memory.
"""

import json
import pytest
from pathlib import Path
from imdbx.models import Episode, SeriesMetadata, TitleInfo


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def make_meta(**kwargs) -> SeriesMetadata:
    defaults = dict(
        title_id         = "tt7441658",
        series_name      = "Black Clover",
        type             = "TV Series",
        years            = "2017–2021",
        content_rating   = "TV-PG",
        episode_duration = "24m",
        imdb_rating      = "8.2/10",
        rating_count     = "47K",
        popularity       = "529",
        tags             = ["Anime", "Action", "Adventure"],
    )
    defaults.update(kwargs)
    return SeriesMetadata(**defaults)


def make_episode(season: int, ep: int) -> Episode:
    return Episode(
        episode_code = f"S{season}.E{ep}",
        title        = f"Episode {ep}",
        season       = season,
        episode      = ep,
        air_date     = "Mon, Jan 1, 2018",
        description  = "A test episode.",
        rating       = "8.0/10",
    )


def make_title_info() -> TitleInfo:
    meta = make_meta()
    return TitleInfo(
        meta    = meta,
        seasons = {
            1: [make_episode(1, i) for i in range(1, 4)],
            2: [make_episode(2, i) for i in range(1, 3)],
        },
    )


# ─── SeriesMetadata ───────────────────────────────────────────────────────────

class TestSeriesMetadata:

    def test_fields_stored(self):
        m = make_meta()
        assert m.title_id    == "tt7441658"
        assert m.series_name == "Black Clover"
        assert m.imdb_rating == "8.2/10"
        assert m.tags        == ["Anime", "Action", "Adventure"]

    def test_optional_fields_default_none(self):
        m = SeriesMetadata(title_id="tt0000001", series_name="Minimal")
        assert m.type             is None
        assert m.years            is None
        assert m.content_rating   is None
        assert m.episode_duration is None
        assert m.imdb_rating      is None
        assert m.rating_count     is None
        assert m.popularity       is None
        assert m.tags             == []

    def test_str_contains_name_and_rating(self):
        m = make_meta()
        s = str(m)
        assert "Black Clover"  in s
        assert "2017–2021"     in s
        assert "8.2/10"        in s

    def test_to_dict_serialisable(self):
        m = make_meta()
        d = m.to_dict()
        json.dumps(d)   # must not raise
        assert d["title_id"]    == "tt7441658"
        assert d["tags"]        == ["Anime", "Action", "Adventure"]


# ─── TitleInfo ────────────────────────────────────────────────────────────────

class TestTitleInfo:

    def test_season_count(self):
        t = make_title_info()
        assert t.season_count() == 2

    def test_episode_count(self):
        t = make_title_info()
        assert t.episode_count() == 5   # 3 + 2

    def test_all_episodes_flat_and_ordered(self):
        t    = make_title_info()
        eps  = t.all_episodes()
        assert len(eps) == 5
        codes = [e.episode_code for e in eps]
        assert codes == ["S1.E1", "S1.E2", "S1.E3", "S2.E1", "S2.E2"]

    def test_get_episode_found(self):
        t  = make_title_info()
        ep = t.get_episode(1, 2)
        assert ep is not None
        assert ep.episode_code == "S1.E2"

    def test_get_episode_not_found_returns_none(self):
        t = make_title_info()
        assert t.get_episode(99, 1) is None
        assert t.get_episode(1, 99) is None

    def test_iter_yields_season_episode_pairs(self):
        t      = make_title_info()
        pairs  = list(t)
        assert len(pairs) == 2
        snum, eps = pairs[0]
        assert snum == 1
        assert len(eps) == 3

    def test_repr_contains_title_id(self):
        t = make_title_info()
        assert "tt7441658" in repr(t)

    def test_str_contains_name_and_counts(self):
        t = make_title_info()
        s = str(t)
        assert "Black Clover" in s
        assert "2"            in s   # seasons
        assert "5"            in s   # episodes


# ─── Save / load round-trip ───────────────────────────────────────────────────

class TestTitleInfoSaveLoad:

    def test_save_creates_valid_json(self, tmp_path: Path):
        t    = make_title_info()
        dest = tmp_path / "output.json"
        t.save(dest)

        assert dest.exists()
        data = json.loads(dest.read_text())
        assert data["title_id"]    == "tt7441658"
        assert data["series_name"] == "Black Clover"
        assert "1" in data["seasons"]

    def test_save_returns_path(self, tmp_path: Path):
        t    = make_title_info()
        dest = tmp_path / "out.json"
        result = t.save(dest)
        assert result == dest

    def test_to_dict_round_trips_cleanly(self):
        t = make_title_info()
        d = t.to_dict()

        # Seasons are string-keyed in the dict (JSON requirement)
        assert "1" in d["seasons"]
        assert "2" in d["seasons"]

        ep = d["seasons"]["1"][0]
        assert ep["episode_code"] == "S1.E1"
        assert ep["title"]        == "Episode 1"
