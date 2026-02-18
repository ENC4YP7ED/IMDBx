"""
tests/test_parse_series_metadata.py
=====================================
Unit tests for parse_series_metadata().
Uses real HTML fragments copied from IMDBx — no network calls.
"""

import pytest
from bs4 import BeautifulSoup
from imdbx._parse import parse_series_metadata


# ─── HTML fixtures ────────────────────────────────────────────────────────────

HERO_HTML = """
<div>
  <h1 data-testid="hero__pageTitle">
    <span class="hero__primary-text">Black Clover</span>
  </h1>
  <ul class="ipc-inline-list" role="presentation">
    <li role="presentation" class="ipc-inline-list__item">TV Series</li>
    <li role="presentation" class="ipc-inline-list__item">
      <a href="/title/tt7441658/releaseinfo/">2017–2021</a>
    </li>
    <li role="presentation" class="ipc-inline-list__item">
      <a href="/title/tt7441658/parentalguide/">TV-PG</a>
    </li>
    <li role="presentation" class="ipc-inline-list__item">24m</li>
  </ul>
</div>
"""

RATING_HTML = """
<div data-testid="hero-rating-bar__aggregate-rating">
  <a href="/title/tt7441658/ratings/">
    <div data-testid="hero-rating-bar__aggregate-rating__score">
      <span class="sc-4dc495c1-1">8.2</span><span>/10</span>
    </div>
  </a>
  <div>8.2 / 10  47K</div>
</div>
<div data-testid="hero-rating-bar__popularity">
  <div data-testid="hero-rating-bar__popularity__score">529</div>
</div>
"""

TAGS_HTML = """
<div class="ipc-chip-list__scroller">
  <a href="/interest/in0000224/?ref_=tt_ov_in_1"><span class="ipc-chip__text">Japanese</span></a>
  <a href="/interest/in0000027/?ref_=tt_ov_in_2"><span class="ipc-chip__text">Anime</span></a>
  <a href="/interest/in0000029/?ref_=tt_ov_in_3"><span class="ipc-chip__text">Hand-Drawn Animation</span></a>
  <a href="/interest/in0000100/?ref_=tt_ov_in_5"><span class="ipc-chip__text">Sword &amp; Sorcery</span></a>
  <a href="/interest/in0000001/?ref_=tt_ov_in_7"><span class="ipc-chip__text">Action</span></a>
</div>
"""

FULL_HTML = HERO_HTML + RATING_HTML + TAGS_HTML


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestParseSeriesName:

    def test_extracts_name_from_testid(self):
        m = parse_series_metadata(soup(HERO_HTML), "tt7441658")
        assert m.series_name == "Black Clover"

    def test_falls_back_to_title_tag(self):
        html = "<title>Black Clover (2017) - IMDBx</title>"
        m    = parse_series_metadata(soup(html), "tt7441658")
        assert m.series_name == "Black Clover"

    def test_falls_back_to_og_title(self):
        html = '<meta property="og:title" content="Black Clover"/>'
        m    = parse_series_metadata(soup(html), "tt7441658")
        assert m.series_name == "Black Clover"

    def test_falls_back_to_title_id_when_nothing_found(self):
        m = parse_series_metadata(soup("<html></html>"), "tt7441658")
        assert m.series_name == "tt7441658"


class TestParseHeroList:

    def test_extracts_type(self):
        m = parse_series_metadata(soup(HERO_HTML), "tt7441658")
        assert m.type == "TV Series"

    def test_extracts_years(self):
        m = parse_series_metadata(soup(HERO_HTML), "tt7441658")
        assert m.years == "2017–2021"

    def test_extracts_content_rating(self):
        m = parse_series_metadata(soup(HERO_HTML), "tt7441658")
        assert m.content_rating == "TV-PG"

    def test_extracts_duration(self):
        m = parse_series_metadata(soup(HERO_HTML), "tt7441658")
        assert m.episode_duration == "24m"

    def test_none_when_hero_absent(self):
        m = parse_series_metadata(soup("<html></html>"), "tt0000001")
        assert m.type             is None
        assert m.years            is None
        assert m.content_rating   is None
        assert m.episode_duration is None


class TestParseRating:

    def test_extracts_imdb_rating(self):
        m = parse_series_metadata(soup(RATING_HTML), "tt7441658")
        assert m.imdb_rating == "8.2/10"

    def test_extracts_vote_count(self):
        m = parse_series_metadata(soup(RATING_HTML), "tt7441658")
        assert m.rating_count == "47K"

    def test_extracts_popularity(self):
        m = parse_series_metadata(soup(RATING_HTML), "tt7441658")
        assert m.popularity == "529"

    def test_none_when_rating_absent(self):
        m = parse_series_metadata(soup("<html></html>"), "tt0000001")
        assert m.imdb_rating  is None
        assert m.rating_count is None
        assert m.popularity   is None


class TestParseTags:

    def test_extracts_all_tags(self):
        m = parse_series_metadata(soup(TAGS_HTML), "tt7441658")
        assert "Japanese"          in m.tags
        assert "Anime"             in m.tags
        assert "Hand-Drawn Animation" in m.tags
        assert "Action"            in m.tags

    def test_html_entity_decoded(self):
        """&amp; in the HTML should become & in the tag text."""
        m = parse_series_metadata(soup(TAGS_HTML), "tt7441658")
        assert "Sword & Sorcery" in m.tags

    def test_tag_order_preserved(self):
        m    = parse_series_metadata(soup(TAGS_HTML), "tt7441658")
        assert m.tags[0] == "Japanese"
        assert m.tags[1] == "Anime"

    def test_empty_list_when_no_interest_links(self):
        m = parse_series_metadata(soup("<html></html>"), "tt0000001")
        assert m.tags == []

    def test_only_interest_links_captured(self):
        """Regular nav links must not appear in tags."""
        html = """
        <a href="/title/tt7441658/">Show page</a>
        <a href="/interest/in0000001/?ref_=tt_ov_in_1">
          <span class="ipc-chip__text">Action</span>
        </a>
        """
        m = parse_series_metadata(soup(html), "tt7441658")
        assert m.tags == ["Action"]


class TestParseFullPage:

    def test_full_page_all_fields(self):
        m = parse_series_metadata(soup(FULL_HTML), "tt7441658")
        assert m.series_name      == "Black Clover"
        assert m.type             == "TV Series"
        assert m.years            == "2017–2021"
        assert m.content_rating   == "TV-PG"
        assert m.episode_duration == "24m"
        assert m.imdb_rating      == "8.2/10"
        assert m.popularity       == "529"
        assert len(m.tags)        >= 3

    def test_title_id_always_stored(self):
        m = parse_series_metadata(soup(FULL_HTML), "tt7441658")
        assert m.title_id == "tt7441658"
