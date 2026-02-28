"""
imdb
====
Public API for the IMDBx scraper package.

Quick start
-----------
    from imdbx import title, season, episode, metadata

    # ── Full series ───────────────────────────────────────────────────────────
    t = title("tt7441658")           # fetch everything (metadata + all seasons)
    print(t)                         # Black Clover [tt7441658] — 4 seasons, 170 episodes

    t.meta.series_name               # "Black Clover"
    t.meta.tags                      # ["Anime", "Action", "Adventure", …]
    t.meta.imdb_rating               # "8.2/10"

    for season_num, episodes in t:
        for ep in episodes:
            print(ep)                # S1.E1 · Asta and Yuno  [7.6/10 (1.6K)]

    t.all_episodes()                 # flat list of every Episode
    t.get_episode(1, 1)              # Episode object for S1E1
    t.save("black_clover.json")      # dump to JSON

    # ── Single season ─────────────────────────────────────────────────────────
    eps = season("tt7441658", 1)     # list[Episode] for season 1 only
    for ep in eps:
        print(ep.title, ep.rating)

    # ── Single episode ────────────────────────────────────────────────────────
    ep = episode("tt7441658", 1, 1)  # Episode S1E1, or None
    print(ep.description)
    print(ep.cover_image)

    # ── Metadata only (no episodes, very fast) ────────────────────────────────
    m = metadata("tt7441658")
    print(m.series_name, m.years, m.tags)

    # ── Saved JSON → TitleInfo ────────────────────────────────────────────────
    t2 = load("black_clover.json")

Available symbols
-----------------
Functions
    title(title_id, ...)     → TitleInfo
    season(title_id, n, ...) → list[Episode]
    episode(title_id, s, e)  → Episode | None
    metadata(title_id)       → SeriesMetadata
    load(path)               → TitleInfo

Dataclasses
    TitleInfo
    SeriesMetadata
    Episode

Debug
    set_debug(True)          enable verbose progress output
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import json
from importlib.metadata import version as _pkg_version, PackageNotFoundError as _PNF

try:
    __version__ = _pkg_version("IMDBx")
except _PNF:
    __version__ = "0.0.0.dev"

# ── Re-export public dataclasses ──────────────────────────────────────────────
from .models import TitleInfo, SeriesMetadata, Episode

# ── Internal engine ───────────────────────────────────────────────────────────
from ._scraper import scrape
from ._http import make_session, http_fetch
from ._parse import parse_series_metadata
from ._log import set_debug
from ._display import print_title

BASE_URL = "https://www.imdb.com"

__all__ = [
    # Public functions
    "title",
    "season",
    "episode",
    "metadata",
    "load",
    "set_debug",
    "print_title",
    # Dataclasses
    "TitleInfo",
    "SeriesMetadata",
    "Episode",
]


# ─────────────────────────────────────────────────────────────────────────────
#  title()
# ─────────────────────────────────────────────────────────────────────────────

def title(
    title_id: str,
    *,
    seasons: list[int] | None = None,
    pool_size: int = 4,
    images_dir: str | Path | None = None,
    download_images: bool = False,
) -> TitleInfo:
    """
    Scrape everything for an IMDBx title and return a :class:`TitleInfo`.

    Parameters
    ----------
    title_id:
        IMDb title ID (the ``tt…`` part of any IMDb URL).
        e.g. ``"tt7441658"`` for Black Clover.
    seasons:
        Optionally restrict to a subset of season numbers.
        ``None`` (default) scrapes all available seasons.
    pool_size:
        Max concurrent browser tabs and image download connections.
        Higher values are faster but use more RAM.  Default: 4.
    images_dir:
        Directory in which to save cover images.
        If ``None`` and ``download_images=False`` (the default), images are
        not downloaded — only the CDN URLs are stored in each Episode.
    download_images:
        Shorthand: set ``True`` to download images into ``"./images/<title_id>/"``.
        Ignored if *images_dir* is explicitly provided.

    Returns
    -------
    TitleInfo
        Fully populated with ``.meta`` (SeriesMetadata) and
        ``.seasons`` (dict[int, list[Episode]]).

    Examples
    --------
        t = title("tt7441658")
        t = title("tt7441658", seasons=[1, 2])
        t = title("tt7441658", download_images=True)
        t = title("tt7441658", images_dir="~/my_images", pool_size=8)
    """
    img_dir: Path | None
    if images_dir is not None:
        img_dir = Path(images_dir).expanduser()
    elif download_images:
        img_dir = Path("images")
    else:
        img_dir = None

    return scrape(
        title_id     = title_id,
        pool_size    = pool_size,
        only_seasons = seasons,
        images_dir   = img_dir,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  season()
# ─────────────────────────────────────────────────────────────────────────────

def season(
    title_id: str,
    season_number: int,
    *,
    pool_size: int = 4,
) -> list[Episode]:
    """
    Scrape a single season and return its episodes.

    This is more efficient than calling ``title()`` when you only need
    one season — it only renders that one page.

    Parameters
    ----------
    title_id:
        IMDBx title ID, e.g. ``"tt7441658"``.
    season_number:
        The season to fetch (1-indexed).
    pool_size:
        Playwright browser pool size.

    Returns
    -------
    list[Episode]
        All episodes for the requested season, in episode order.
        Returns an empty list if the season does not exist.

    Examples
    --------
        eps = season("tt7441658", 1)
        for ep in eps:
            print(ep.title, ep.rating)
    """
    info = scrape(
        title_id     = title_id,
        pool_size    = pool_size,
        only_seasons = [season_number],
        images_dir   = None,
    )
    return info.seasons.get(season_number, [])


# ─────────────────────────────────────────────────────────────────────────────
#  episode()
# ─────────────────────────────────────────────────────────────────────────────

def episode(
    title_id: str,
    season_number: int,
    episode_number: int,
    *,
    pool_size: int = 4,
) -> Optional[Episode]:
    """
    Fetch a single episode by season and episode number.

    Fetches only the necessary season page, then returns the matching episode.

    Parameters
    ----------
    title_id:
        IMDBx title ID, e.g. ``"tt7441658"``.
    season_number:
        Season number (1-indexed).
    episode_number:
        Episode number within the season (1-indexed).
    pool_size:
        Playwright browser pool size.

    Returns
    -------
    Episode or None
        The matching Episode dataclass, or ``None`` if not found.

    Examples
    --------
        ep = episode("tt7441658", 1, 1)
        if ep:
            print(ep.title)       # "Asta and Yuno"
            print(ep.rating)      # "7.6/10 (1.6K)"
            print(ep.description)
            print(ep.air_date)
    """
    episodes = season(title_id, season_number, pool_size=pool_size)
    for ep in episodes:
        if ep.episode == episode_number:
            return ep
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  metadata()
# ─────────────────────────────────────────────────────────────────────────────

def metadata(title_id: str) -> SeriesMetadata:
    """
    Fetch only the series-level metadata — no episode scraping.

    Much faster than ``title()`` because it only makes one HTTP request
    and does not launch a browser.

    Returns
    -------
    SeriesMetadata
        Populated with name, type, years, rating, tags, popularity, etc.

    Examples
    --------
        m = metadata("tt7441658")
        print(m.series_name)    # "Black Clover"
        print(m.tags)           # ["Anime", "Action", "Adventure", …]
        print(m.imdb_rating)    # "8.2/10"
        print(m.years)          # "2017–2021"
        print(m.content_rating) # "TV-PG"
    """
    session = make_session(4)
    try:
        soup = http_fetch(f"{BASE_URL}/title/{title_id}/", session)
        if soup is None:
            return SeriesMetadata(title_id=title_id, series_name=title_id)
        return parse_series_metadata(soup, title_id)
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
#  load()
# ─────────────────────────────────────────────────────────────────────────────

def load(path: str | Path) -> TitleInfo:
    """
    Load a previously saved JSON file back into a :class:`TitleInfo` object.

    The JSON format is the one produced by ``TitleInfo.save()`` or
    ``title(...).save("output.json")``.

    Parameters
    ----------
    path:
        Path to the JSON file.

    Returns
    -------
    TitleInfo

    Examples
    --------
        t = title("tt7441658")
        t.save("black_clover.json")

        # Later, in another script:
        t2 = load("black_clover.json")
        print(t2.meta.series_name)
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    meta = SeriesMetadata(
        title_id         = data.get("title_id", ""),
        series_name      = data.get("series_name", ""),
        type             = data.get("type"),
        years            = data.get("years"),
        content_rating   = data.get("content_rating"),
        episode_duration = data.get("episode_duration"),
        imdb_rating      = data.get("imdb_rating"),
        rating_count     = data.get("rating_count"),
        popularity       = data.get("popularity"),
        tags             = data.get("tags", []),
    )

    seasons: dict[int, list[Episode]] = {}
    for season_key, eps in data.get("seasons", {}).items():
        seasons[int(season_key)] = [
            Episode(
                episode_code       = ep.get("episode_code", ""),
                title              = ep.get("title", ""),
                season             = ep.get("season", 0),
                episode            = ep.get("episode", 0),
                air_date           = ep.get("air_date", ""),
                description        = ep.get("description", ""),
                rating             = ep.get("rating", "N/A"),
                cover_image        = ep.get("cover_image"),
                cover_image_local  = ep.get("cover_image_local"),
                imdb_url           = ep.get("imdb_url", ""),
            )
            for ep in eps
        ]

    return TitleInfo(meta=meta, seasons=seasons)
