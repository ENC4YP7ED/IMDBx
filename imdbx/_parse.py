"""
imdbx._parse
===========
All BeautifulSoup parsing logic.

Two public entry points
-----------------------
parse_series_metadata(soup, title_id)  → SeriesMetadata
parse_episodes(soup)                   → Generator[Episode]

Design rule: zero hardcoded CSS class names.
Every selector uses data-testid attributes, structural patterns,
or regex matches on text/href content so the parsers survive IMDBx redesigns.
"""

from __future__ import annotations

import re
from collections.abc import Generator
from typing import Any

from bs4 import BeautifulSoup, Tag

from .models import Episode, SeriesMetadata

BASE_URL = "https://www.imdb.com"


# ══════════════════════════════════════════════════════════════════════════════
#  Series metadata
# ══════════════════════════════════════════════════════════════════════════════

def parse_series_metadata(soup: BeautifulSoup, title_id: str) -> SeriesMetadata:
    """
    Extract all series-level fields from the IMDBx title page hero section.

    Fields extracted
    ----------------
    series_name      data-testid="hero__pageTitle"  (falls back to <title> / og:title)
    type             inline hero <ul>  e.g. "TV Series"
    years            inline hero <ul>  e.g. "2017–2021"
    content_rating   inline hero <ul>  e.g. "TV-PG"
    episode_duration inline hero <ul>  e.g. "24m"
    imdb_rating      data-testid="hero-rating-bar__aggregate-rating__score"
    rating_count     regex on aggregate rating container text
    popularity       data-testid="hero-rating-bar__popularity__score"
    tags             <a href="/interest/…"> links (most stable selector)
    """
    meta = SeriesMetadata(title_id=title_id, series_name=title_id)

    # ── Series name ───────────────────────────────────────────────────────────
    node = soup.find(attrs={"data-testid": "hero__pageTitle"})
    if node:
        name = node.get_text(strip=True)
        if name:
            meta.series_name = name
    else:
        tag = soup.find("title")
        if tag:
            raw = re.sub(r"\s*-\s*IMDBx\s*$", "", tag.get_text(strip=True), flags=re.I)
            raw = re.sub(r"\s*\(\d{4}.*?\)\s*$", "", raw).strip()
            if raw:
                meta.series_name = raw
        else:
            og = soup.find("meta", attrs={"property": "og:title"})
            if og and og.get("content"):
                meta.series_name = og["content"].strip()

    # ── Inline hero list: type · years · content_rating · duration ────────────
    hero_node = soup.find(attrs={"data-testid": "hero__pageTitle"})
    if hero_node:
        ul = hero_node.parent.find("ul") if hero_node.parent else None
        if ul:
            for item in (li.get_text(strip=True) for li in ul.find_all("li")):
                # content_rating checked FIRST — "TV-PG" would also match "TV\s" otherwise
                if re.match(r"TV-(G|PG|14|MA)|^(G|PG|PG-13|R|NC-17)$", item, re.I):
                    meta.content_rating = item
                elif re.match(r"TV\s|Movie|Short|Special|Mini", item, re.I):
                    meta.type = item
                elif re.match(r"\d{4}", item):
                    meta.years = item
                elif re.search(r"\d+\s*(h|m)", item):
                    meta.episode_duration = item

    # ── IMDBx rating + vote count ───────────────────────────────────────────────
    agg = soup.find(attrs={"data-testid": "hero-rating-bar__aggregate-rating"})
    if agg:
        score_div = agg.find(attrs={"data-testid": "hero-rating-bar__aggregate-rating__score"})
        if score_div:
            spans = score_div.find_all("span")
            if spans:
                meta.imdb_rating = spans[0].get_text(strip=True) + "/10"
        # Vote count follows the LAST "/10" occurrence in the container text
        # (the first "/10" is from the score span and is followed by the repeated
        # rating number, not the vote count)
        all_matches = re.findall(r"/\s*10\s+([\d.,KkMm]+)", agg.get_text(" ", strip=True))
        if all_matches:
            meta.rating_count = all_matches[-1]

    # ── Popularity ────────────────────────────────────────────────────────────
    pop = soup.find(attrs={"data-testid": "hero-rating-bar__popularity__score"})
    if pop:
        meta.popularity = pop.get_text(strip=True)

    # ── Tags via /interest/ href pattern ─────────────────────────────────────
    # Every interest/genre tag links to /interest/inXXXXXXX/ — this structural
    # pattern is far more stable than any CSS class name.
    seen: set[str] = set()
    tags: list[str] = []
    for a in soup.find_all("a", href=re.compile(r"^/interest/in\d+")):
        text = a.get_text(strip=True)
        if text and text not in seen:
            seen.add(text)
            tags.append(text)
    if tags:
        meta.tags = tags

    return meta


# ══════════════════════════════════════════════════════════════════════════════
#  Episode card helpers
# ══════════════════════════════════════════════════════════════════════════════

def _best_image(img: Tag) -> str | None:
    """
    Pick the highest-resolution URL from a srcset attribute, falling back to src.

    IMDBx CDN URLs contain commas internally, e.g. ...CR0,0,1000,563_.jpg 1000w
    We split only on ", https://" boundaries to preserve embedded commas.
    """
    srcset = img.get("srcset", "")
    if srcset:
        entries = re.split(r",\s+(?=https?://)", srcset.strip())
        candidates: list[tuple[int, str]] = []
        for entry in entries:
            tokens = entry.rsplit(None, 1)
            if len(tokens) == 2:
                url, descriptor = tokens
                try:
                    width = int(re.sub(r"[^\d]", "", descriptor))
                    candidates.append((width, url.strip()))
                except ValueError:
                    pass
        if candidates:
            return max(candidates)[1]
    return img.get("src")


def _find_episode_cards(soup: BeautifulSoup) -> list[Tag]:
    """
    Return only genuine episode <article> cards.

    An episode card must contain both:
    • A link matching  /title/tt[0-9]+/?ref_=ttep
    • The S#.E# title text pattern
    """
    SE      = re.compile(r"S\d+\.E\d+", re.I)
    EP_LINK = re.compile(r"/title/tt\d+/\?ref_=ttep")

    cards = [
        a for a in soup.find_all("article")
        if a.find("a", href=EP_LINK) and SE.search(a.get_text())
    ]
    if cards:
        return cards

    # Fallback 1: data-testid containing "episode"
    cards = [
        t for t in soup.find_all(attrs={"data-testid": re.compile(r"episode", re.I)})
        if SE.search(t.get_text())
    ]
    if cards:
        return cards

    # Fallback 2: any article with S#.E# text
    return [a for a in soup.find_all("article") if SE.search(a.get_text())]


def _find_title_text(card: Tag) -> str:
    node = card.find(attrs={"data-testid": "slate-list-card-title"})
    if node:
        return node.get_text(strip=True)
    SE = re.compile(r"S\d+\.E\d+", re.I)
    for tag in card.find_all(["div", "h4", "h3", "span"]):
        text = tag.get_text(strip=True)
        if SE.search(text) and len(text) < 200:
            return text
    link = card.find("a", attrs={"aria-label": True})
    return link["aria-label"] if link else ""


def _find_air_date(card: Tag) -> str:
    DATE = re.compile(
        r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+\w+\s+\d+,\s+\d{4}"
        r"|\d{1,2}\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2}",
        re.I,
    )
    for tag in card.find_all(["span", "div", "time"]):
        text = tag.get_text(strip=True)
        if DATE.search(text) and len(text) < 50:
            return text
    for tag in card.find_all(["span", "div"]):
        cls = " ".join(tag.get("class", []))
        if "date" in cls.lower() or "air" in cls.lower():
            return tag.get_text(strip=True)
    return ""


def _find_description(card: Tag) -> str:
    for testid in ("plot", "synopsis", "description", "html-content"):
        node = card.find(attrs={"data-testid": re.compile(testid, re.I)})
        if node:
            return node.get_text(strip=True)
    for div in card.find_all("div", role="presentation"):
        text = div.get_text(strip=True)
        if len(text) > 30:
            return text
    SE   = re.compile(r"S\d+\.E\d+")
    DATE = re.compile(r"\d{4}|Mon|Tue|Wed|Thu|Fri|Sat|Sun", re.I)
    candidates = []
    for tag in card.find_all(["div", "p"]):
        if tag.find(["div", "p"]):
            continue
        text = tag.get_text(strip=True)
        if len(text) > 30 and not SE.search(text) and not DATE.search(text[:15]):
            candidates.append(text)
    return max(candidates, key=len) if candidates else ""


def _find_rating(card: Tag) -> str:
    for testid in ("ratingGroup--imdb-rating", "ratingGroup--container"):
        node = card.find(attrs={"data-testid": testid})
        if node:
            m = re.search(r"([\d.]+)", node.get("aria-label", ""))
            if m:
                full = node.get_text(" ", strip=True)
                vm   = re.search(r"\(\s*([\d.,KkMm]+)\s*\)", full)
                votes = vm.group(1) if vm else ""
                return f"{m.group(1)}/10 ({votes})" if votes else f"{m.group(1)}/10"
    node = card.find("span", attrs={"aria-label": re.compile(r"IMDBx rating", re.I)})
    if node:
        m = re.search(r"([\d.]+)", node.get("aria-label", ""))
        if m:
            return f"{m.group(1)}/10"
    full = card.get_text(" ")
    m = re.search(r"\b(\d\.\d)\s*/\s*10\b", full)
    if m:
        vm    = re.search(r"\(\s*([\d.,KkMm]+)\s*\)", full)
        votes = vm.group(1) if vm else ""
        return f"{m.group(1)}/10 ({votes})" if votes else f"{m.group(1)}/10"
    return "N/A"


def _find_cover_image(card: Tag) -> str | None:
    for img in card.find_all("img"):
        if "media-amazon.com" in img.get("srcset", "") + img.get("src", ""):
            return _best_image(img)
    for img in card.find_all("img"):
        try:
            if int(img.get("width", 0)) >= 80:
                return _best_image(img)
        except ValueError:
            pass
        src = img.get("src", "")
        if src and not src.endswith(".svg") and "icon" not in src.lower():
            return _best_image(img)
    return None


def _find_episode_link(card: Tag) -> str:
    for a in card.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/title/tt\d+/", href) and "ref_=ttep" in href:
            return (BASE_URL + href) if href.startswith("/") else href
    a = card.find("a", href=re.compile(r"/title/tt\d+/"))
    if a:
        href = a["href"]
        return (BASE_URL + href) if href.startswith("/") else href
    return ""


# ══════════════════════════════════════════════════════════════════════════════
#  Episode generator
# ══════════════════════════════════════════════════════════════════════════════

def parse_episodes(soup: BeautifulSoup) -> Generator[Episode, None, None]:
    """
    Lazy generator — yields one fully-parsed Episode dataclass per card.
    """
    for card in _find_episode_cards(soup):
        raw   = _find_title_text(card)
        parts = re.split(r"\s*[∙·]\s*", raw, maxsplit=1)

        episode_code = parts[0].strip() if parts else ""
        ep_title     = parts[1].strip() if len(parts) > 1 else raw

        m = re.match(r"S(\d+)\.E(\d+)", episode_code, re.I)
        season_num  = int(m.group(1)) if m else 0
        episode_num = int(m.group(2)) if m else 0

        yield Episode(
            episode_code       = episode_code,
            title              = ep_title,
            season             = season_num,
            episode            = episode_num,
            air_date           = _find_air_date(card),
            description        = _find_description(card),
            rating             = _find_rating(card),
            cover_image        = _find_cover_image(card),
            cover_image_local  = None,
            imdb_url           = _find_episode_link(card),
        )


# ══════════════════════════════════════════════════════════════════════════════
#  Season discovery
# ══════════════════════════════════════════════════════════════════════════════

def parse_season_numbers(soup: BeautifulSoup) -> list[int]:
    """
    Extract all available season numbers from the IMDBx episodes index page.

    Three strategies, no hardcoded class names:
    1. data-testid="tab-season-entry"
    2. <select>/<option> season picker
    3. Any href containing ?season=N
    """
    found: set[int] = set()

    for tag in soup.find_all(attrs={"data-testid": "tab-season-entry"}):
        t = tag.get_text(strip=True)
        if t.isdigit():
            found.add(int(t))

    if not found:
        for opt in soup.select("select option"):
            v = opt.get("value", "").strip()
            if v.isdigit():
                found.add(int(v))

    if not found:
        for a in soup.find_all("a", href=re.compile(r"\?season=\d+")):
            m = re.search(r"\?season=(\d+)", a["href"])
            if m:
                found.add(int(m.group(1)))

    return sorted(found)
