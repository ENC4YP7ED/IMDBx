"""
tests/test_parse_episode_cards.py
===================================
Unit tests for parse_episodes() and its helpers.
Uses real-ish HTML fragments — no network, no browser.
"""

import pytest
from bs4 import BeautifulSoup
from imdbx._parse import parse_episodes, parse_season_numbers


# ─── Minimal episode card HTML (mirrors real IMDBx structure) ──────────────────

def make_card_html(
    code="S1.E1",
    title="Asta and Yuno",
    air_date="Tue, Oct 3, 2017",
    description="Two young boys dream of becoming the Wizard King.",
    rating_val="7.6",
    votes="1.6K",
    img_url="https://m.media-amazon.com/images/S1E1.jpg",
    episode_tt="tt7462664",
) -> str:
    return f"""
    <article>
      <a href="/title/{episode_tt}/?ref_=ttep_ep1">
        <img src="{img_url}" width="120" alt="cover"/>
      </a>
      <div data-testid="slate-list-card-title">
        {code} ∙ {title}
      </div>
      <span>{air_date}</span>
      <div data-testid="plot">{description}</div>
      <div data-testid="ratingGroup--imdbx-rating"
           aria-label="IMDBx rating: {rating_val}">
        {rating_val}/10 ({votes})
      </div>
    </article>
    """


def make_season_html(*cards) -> BeautifulSoup:
    return BeautifulSoup("".join(cards), "html.parser")


# ─── Tests: parse_episodes ────────────────────────────────────────────────────

class TestParseEpisodesBasic:

    def test_yields_one_episode_per_card(self):
        s   = make_season_html(make_card_html(), make_card_html("S1.E2", "Episode Two", episode_tt="tt0000002"))
        eps = list(parse_episodes(s))
        assert len(eps) == 2

    def test_episode_code_parsed(self):
        s  = make_season_html(make_card_html("S2.E5", "Test"))
        ep = list(parse_episodes(s))[0]
        assert ep.episode_code == "S2.E5"

    def test_title_parsed(self):
        s  = make_season_html(make_card_html(title="Asta and Yuno"))
        ep = list(parse_episodes(s))[0]
        assert ep.title == "Asta and Yuno"

    def test_season_number_extracted(self):
        s  = make_season_html(make_card_html("S3.E7"))
        ep = list(parse_episodes(s))[0]
        assert ep.season  == 3
        assert ep.episode == 7

    def test_air_date_extracted(self):
        s  = make_season_html(make_card_html(air_date="Mon, Apr 4, 2022"))
        ep = list(parse_episodes(s))[0]
        assert ep.air_date == "Mon, Apr 4, 2022"

    def test_description_extracted(self):
        s  = make_season_html(make_card_html(description="A young orphan seeks greatness."))
        ep = list(parse_episodes(s))[0]
        assert ep.description == "A young orphan seeks greatness."

    def test_rating_extracted(self):
        s  = make_season_html(make_card_html(rating_val="8.5", votes="2K"))
        ep = list(parse_episodes(s))[0]
        assert "8.5" in ep.rating
        assert "10"  in ep.rating

    def test_cover_image_extracted(self):
        url = "https://m.media-amazon.com/images/test.jpg"
        s   = make_season_html(make_card_html(img_url=url))
        ep  = list(parse_episodes(s))[0]
        assert ep.cover_image == url

    def test_imdb_url_extracted(self):
        s  = make_season_html(make_card_html(episode_tt="tt1234567"))
        ep = list(parse_episodes(s))[0]
        assert "tt1234567" in ep.imdb_url

    def test_cover_image_local_is_none_initially(self):
        s  = make_season_html(make_card_html())
        ep = list(parse_episodes(s))[0]
        assert ep.cover_image_local is None


class TestParseEpisodesEdgeCases:

    def test_empty_soup_yields_nothing(self):
        s   = BeautifulSoup("<html></html>", "html.parser")
        eps = list(parse_episodes(s))
        assert eps == []

    def test_non_episode_articles_ignored(self):
        """Articles without S#.E# should be filtered out."""
        html = """
        <article><p>Some promo content</p></article>
        <article>
          <a href="/title/tt0000001/?ref_=ttep_ep1">link</a>
          <div data-testid="slate-list-card-title">S1.E1 ∙ Real Episode</div>
          <div data-testid="ratingGroup--imdbx-rating" aria-label="IMDBx rating: 7.0">7.0/10</div>
        </article>
        """
        eps = list(parse_episodes(BeautifulSoup(html, "html.parser")))
        assert len(eps) == 1
        assert eps[0].title == "Real Episode"

    def test_multiple_episodes_preserve_order(self):
        cards = [make_card_html(f"S1.E{i}", f"Episode {i}", episode_tt=f"tt000000{i}") for i in range(1, 6)]
        s     = make_season_html(*cards)
        eps   = list(parse_episodes(s))
        assert [ep.episode for ep in eps] == [1, 2, 3, 4, 5]


# ─── Tests: parse_season_numbers ─────────────────────────────────────────────

class TestParseSeasonNumbers:

    def test_reads_tab_season_entry(self):
        html = """
        <div data-testid="tab-season-entry">1</div>
        <div data-testid="tab-season-entry">2</div>
        <div data-testid="tab-season-entry">3</div>
        """
        nums = parse_season_numbers(BeautifulSoup(html, "html.parser"))
        assert nums == [1, 2, 3]

    def test_reads_select_options(self):
        html = """
        <select>
          <option value="1">Season 1</option>
          <option value="2">Season 2</option>
        </select>
        """
        nums = parse_season_numbers(BeautifulSoup(html, "html.parser"))
        assert nums == [1, 2]

    def test_reads_href_season_param(self):
        html = """
        <a href="/title/tt0000001/episodes/?season=1">S1</a>
        <a href="/title/tt0000001/episodes/?season=4">S4</a>
        """
        nums = parse_season_numbers(BeautifulSoup(html, "html.parser"))
        assert nums == [1, 4]

    def test_returns_sorted_list(self):
        html = """
        <div data-testid="tab-season-entry">3</div>
        <div data-testid="tab-season-entry">1</div>
        <div data-testid="tab-season-entry">2</div>
        """
        nums = parse_season_numbers(BeautifulSoup(html, "html.parser"))
        assert nums == [1, 2, 3]

    def test_empty_page_returns_empty_list(self):
        nums = parse_season_numbers(BeautifulSoup("<html></html>", "html.parser"))
        assert nums == []

    def test_deduplicates_season_numbers(self):
        html = """
        <div data-testid="tab-season-entry">1</div>
        <div data-testid="tab-season-entry">1</div>
        <div data-testid="tab-season-entry">2</div>
        """
        nums = parse_season_numbers(BeautifulSoup(html, "html.parser"))
        assert nums == [1, 2]
