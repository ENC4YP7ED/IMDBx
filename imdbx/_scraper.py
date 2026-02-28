"""
imdbx._scraper
=============
Orchestration layer — wires together _http, _browser, and _parse.

This module is the internal engine.  End users call the clean functions
in imdbx/__init__.py instead.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from pathlib import Path
from typing import Any

from ._http    import make_session, http_fetch, download_images
from ._browser import fetch_seasons_async
from ._parse   import parse_series_metadata, parse_season_numbers, parse_episodes
from ._log     import dbg, c, C
from .models import TitleInfo, Episode, SeriesMetadata

BASE_URL = "https://www.imdb.com"


# ─── Season number discovery ──────────────────────────────────────────────────

def get_season_numbers(title_id: str, pool_size: int = 4) -> list[int]:
    """
    Return a sorted list of available season numbers for *title_id*.
    Uses a lightweight HTTP fetch — no browser required.
    """
    session = make_session(pool_size)
    try:
        soup = http_fetch(f"{BASE_URL}/title/{title_id}/episodes/", session)
        return parse_season_numbers(soup) if soup else []
    finally:
        session.close()


# ─── Lazy generators ──────────────────────────────────────────────────────────

def iter_seasons(
    title_id: str,
    season_nums: list[int],
    pool_size: int = 4,
) -> Generator[tuple[int, list[Episode]], None, None]:
    """
    Lazy generator — yields ``(season_number, episodes)`` as each page
    finishes rendering.  Uses a concurrent Playwright browser pool.
    """
    results = asyncio.run(
        fetch_seasons_async(title_id, season_nums, pool_size, BASE_URL)
    )
    for season_num, soup in results:
        if soup is None:
            dbg(c(f"  ✗  Season {season_num} failed — skipping.", C.RED))
            continue
        episodes = list(parse_episodes(soup))
        dbg(f"     {c('✓', C.BGREEN)}  Season {c(season_num, C.BYELLOW, C.BOLD)}: "
            f"{c(len(episodes), C.BWHITE, C.BOLD)} episode(s) parsed.")
        yield season_num, episodes


# ─── Main scraper ─────────────────────────────────────────────────────────────

def scrape(
    title_id: str,
    pool_size: int = 4,
    only_seasons: list[int] | None = None,
    images_dir: Path | None = Path("images"),
) -> TitleInfo:
    """
    Full scrape for *title_id*.  Orchestrates all three layers:

    Layer 1 (niquests) — metadata + season list discovery
    Layer 2 (Playwright) — JS-rendered season pages + load-more expansion
    Layer 3 (niquests async) — concurrent cover image downloading

    Parameters
    ----------
    title_id:
        IMDBx title ID, e.g. ``"tt7441658"`` for Black Clover.
    pool_size:
        Max concurrent browser tabs / image downloads.
    only_seasons:
        If given, scrape only these season numbers.
    images_dir:
        Directory to save cover images.  Pass ``None`` to skip downloading.

    Returns
    -------
    TitleInfo
        Fully populated object with ``.meta`` and ``.seasons``.
    """

    # ── Layer 1: metadata + season discovery ──────────────────────────────────
    session = make_session(pool_size)
    print(f"\n{c('◈  Discovering', C.BCYAN, C.BOLD)} {c(title_id, C.BYELLOW, C.BOLD)} …")

    from bs4 import BeautifulSoup

    meta_soup = http_fetch(f"{BASE_URL}/title/{title_id}/", session)
    meta      = parse_series_metadata(meta_soup, title_id) if meta_soup else \
                SeriesMetadata(title_id=title_id, series_name=title_id)

    season_soup = http_fetch(f"{BASE_URL}/title/{title_id}/episodes/", session)
    all_seasons = parse_season_numbers(season_soup or BeautifulSoup("", "html.parser"))
    session.close()

    # Print discovered metadata
    print(f"  {c(meta.series_name, C.BWHITE, C.BOLD)}", end="")
    if meta.years:
        print(f"  {c(meta.years, C.DIM)}", end="")
    if meta.type:
        print(f"  {c('·', C.DIM)} {c(meta.type, C.DIM)}", end="")
    print()
    if meta.imdb_rating:
        votes = f"  ({meta.rating_count} votes)" if meta.rating_count else ""
        pop   = f"   Popularity: #{meta.popularity}" if meta.popularity else ""
        print(f"  {c('★', C.BYELLOW)} {c(meta.imdb_rating, C.BYELLOW, C.BOLD)}{votes}{pop}")
    if meta.tags:
        print(f"  {c(' | '.join(meta.tags), C.DIM)}")

    if not all_seasons:
        print(c("  ⚠  No seasons found — falling back to season 1.", C.YELLOW))
        all_seasons = [1]

    target = [s for s in all_seasons if s in only_seasons] if only_seasons else all_seasons
    print(f"  {c('✓', C.BGREEN)}  Found {c(len(all_seasons), C.BYELLOW, C.BOLD)} "
          f"season(s): {c(all_seasons, C.WHITE)}")
    print(f"  {c('↳', C.BCYAN)}  Scraping: {c(target, C.BCYAN)}  "
          f"{c(f'(pool_size={pool_size})', C.DIM)}\n")

    # ── Layer 2: browser scraping ─────────────────────────────────────────────
    info = TitleInfo(meta=meta)
    for season_num, episodes in iter_seasons(title_id, target, pool_size):
        info.seasons[season_num] = episodes
    info.seasons = dict(sorted(info.seasons.items()))

    # ── Layer 3: image downloading ────────────────────────────────────────────
    if images_dir is not None:
        download_images(info, images_dir, pool_size=pool_size * 2)

    return info
