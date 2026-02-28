"""
IMDBx feature demo
──────────────────
Exercises every public API function against a real IMDb title.

Usage:
    python demo.py                     # runs all demos (Breaking Bad)
    python demo.py tt0903747           # use a different title ID
    python demo.py tt0903747 --debug   # with verbose output
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import imdbx
from imdbx import (
    title,
    season,
    episode,
    metadata,
    load,
    set_debug,
    TitleInfo,
    SeriesMetadata,
    Episode,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def banner(text: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {text}")
    print('─' * 60)

def ok(label: str, value=None) -> None:
    suffix = f"  →  {value}" if value is not None else ""
    print(f"  ✓  {label}{suffix}")

def check(condition: bool, label: str) -> None:
    icon = "✓" if condition else "✗"
    print(f"  {icon}  {label}")
    assert condition, f"FAILED: {label}"


# ── 1. metadata() ─────────────────────────────────────────────────────────────

def demo_metadata(tt: str) -> SeriesMetadata:
    banner("1 · metadata()  — series info only, no browser")
    m = metadata(tt)
    assert isinstance(m, SeriesMetadata)
    ok("returns SeriesMetadata", type(m).__name__)
    check(bool(m.series_name),   f"series_name = {m.series_name!r}")
    check(bool(m.title_id),      f"title_id    = {m.title_id!r}")
    ok("type",             m.type)
    ok("years",            m.years)
    ok("content_rating",   m.content_rating)
    ok("episode_duration", m.episode_duration)
    ok("imdb_rating",      m.imdb_rating)
    ok("rating_count",     m.rating_count)
    ok("popularity",       m.popularity)
    ok("tags",             m.tags)
    d = m.to_dict()
    check(isinstance(d, dict), "to_dict() returns dict")
    check(json.dumps(d) is not None, "to_dict() is JSON-serialisable")
    return m


# ── 2. season() ───────────────────────────────────────────────────────────────

def demo_season(tt: str) -> list[Episode]:
    banner("2 · season()  — single season, browser required")
    eps = season(tt, 1)
    assert isinstance(eps, list)
    check(len(eps) > 0, f"season 1 returned {len(eps)} episode(s)")
    ep = eps[0]
    assert isinstance(ep, Episode)
    ok("first episode", ep)
    check(bool(ep.episode_code),  f"episode_code = {ep.episode_code!r}")
    check(bool(ep.title),         f"title        = {ep.title!r}")
    check(ep.season == 1,         f"season       = {ep.season}")
    check(ep.episode >= 1,        f"episode      = {ep.episode}")
    ok("air_date",    ep.air_date)
    ok("rating",      ep.rating)
    ok("description", ep.description[:60] + "…" if ep.description else "")
    ok("cover_image", ep.cover_image)
    ok("imdb_url",    ep.imdb_url)
    check(isinstance(ep.to_dict(), dict), "to_dict() returns dict")
    return eps


# ── 3. episode() ──────────────────────────────────────────────────────────────

def demo_episode(tt: str) -> Episode:
    banner("3 · episode()  — single episode lookup")
    ep = episode(tt, 1, 1)
    assert ep is not None
    assert isinstance(ep, Episode)
    check(ep.season == 1 and ep.episode == 1, f"got S1E1: {ep.episode_code}")
    ok("title", ep.title)
    none_ep = episode(tt, 99, 99)
    check(none_ep is None, "returns None for non-existent episode")
    return ep


# ── 4. title() ────────────────────────────────────────────────────────────────

def demo_title(tt: str) -> TitleInfo:
    banner("4 · title()  — full scrape, all seasons")
    t = title(tt, seasons=[1, 2])
    assert isinstance(t, TitleInfo)
    assert isinstance(t.meta, SeriesMetadata)
    ok("returns TitleInfo", repr(t))
    check(t.season_count() >= 2, f"season_count() = {t.season_count()}")
    check(t.episode_count() > 0, f"episode_count() = {t.episode_count()}")

    # all_episodes()
    flat = t.all_episodes()
    check(isinstance(flat, list) and len(flat) == t.episode_count(),
          f"all_episodes() returned {len(flat)} episodes")

    # get_episode()
    ep = t.get_episode(1, 1)
    check(ep is not None and ep.season == 1 and ep.episode == 1,
          "get_episode(1, 1) found S1E1")

    # iteration
    pairs = list(t)
    check(len(pairs) >= 2, f"__iter__ yielded {len(pairs)} (season, episodes) pairs")

    # __str__ / __repr__
    check(t.meta.series_name in str(t), f"str(t) = {str(t)!r}")
    check("TitleInfo" in repr(t),       f"repr(t) = {repr(t)!r}")
    return t


# ── 5. save() / load() ────────────────────────────────────────────────────────

def demo_save_load(t: TitleInfo) -> TitleInfo:
    banner("5 · TitleInfo.save()  /  load()")
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)

    saved = t.save(path)
    check(saved == path,          f"save() returned path {saved}")
    check(path.exists(),          "JSON file was created")
    check(path.stat().st_size > 0, "JSON file is non-empty")

    t2 = load(path)
    assert isinstance(t2, TitleInfo)
    check(t2.meta.series_name == t.meta.series_name,
          f"series_name round-trips: {t2.meta.series_name!r}")
    check(t2.season_count() == t.season_count(),
          f"season_count round-trips: {t2.season_count()}")
    check(t2.episode_count() == t.episode_count(),
          f"episode_count round-trips: {t2.episode_count()}")

    path.unlink()
    ok("temp file cleaned up")
    return t2


# ── 6. dataclass field checks ─────────────────────────────────────────────────

def demo_dataclasses() -> None:
    banner("6 · dataclass construction  — all fields, defaults, str/repr")
    ep = Episode(
        episode_code="S1.E1",
        title="Pilot",
        season=1,
        episode=1,
        air_date="Sun, Jan 20, 2008",
        description="A chemistry teacher turns to cooking meth.",
        rating="7.8/10 (120K)",
        cover_image="https://m.media-amazon.com/images/test.jpg",
        cover_image_local=None,
        imdb_url="https://www.imdb.com/title/tt0959621/",
    )
    check("S1.E1" in str(ep) and "Pilot" in str(ep), f"str(Episode) = {str(ep)!r}")
    check(ep.cover_image_local is None, "cover_image_local defaults to None")

    m = SeriesMetadata(title_id="tt0903747", series_name="Breaking Bad")
    check(m.imdb_rating is None, "optional fields default to None")
    check(m.tags == [],          "tags defaults to []")
    check("Breaking Bad" in str(m), f"str(SeriesMetadata) = {str(m)!r}")

    ok("Episode and SeriesMetadata construct correctly")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="IMDBx feature demo")
    parser.add_argument("title_id", nargs="?", default="tt0903747",
                        help="IMDb title ID (default: Breaking Bad)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable verbose IMDBx debug output")
    args = parser.parse_args()

    if args.debug:
        set_debug(True)

    tt = args.title_id
    print(f"\nIMDBx v{imdbx.__version__ if hasattr(imdbx, '__version__') else '?'}"
          f"  —  testing against {tt}\n")

    # lightweight checks first (no browser)
    demo_dataclasses()
    m = demo_metadata(tt)

    # browser-based (Chromium required)
    eps  = demo_season(tt)
    ep   = demo_episode(tt)
    t    = demo_title(tt)
    demo_save_load(t)

    print(f"\n{'═' * 60}")
    print(f"  All demos passed  ✓")
    print(f"{'═' * 60}\n")


if __name__ == "__main__":
    main()
