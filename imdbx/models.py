"""
imdbx.models
===========
Typed dataclasses that represent every piece of data this package returns.

These are the objects you work with after calling any public API function:

    from imdbx import title
    t = title("tt7441658")

    t                       → TitleInfo
    t.seasons[1]            → list[Episode]
    t.seasons[1][0]         → Episode
    t.meta                  → SeriesMetadata
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import json


# ─── Episode ──────────────────────────────────────────────────────────────────

@dataclass
class Episode:
    """A single episode of a TV series."""

    # Identity
    episode_code: str          # "S1.E1"
    title:        str          # "Asta and Yuno"
    season:       int          # 1
    episode:      int          # 1

    # Content
    air_date:    str           # "Tue, Oct 3, 2017"  (empty string if unknown)
    description: str           # plot summary        (empty string if unknown)
    rating:      str           # "7.6/10 (1.6K)"    ("N/A" if unrated)

    # Media
    cover_image:       Optional[str] = None   # CDN URL
    cover_image_local: Optional[str] = None   # local path after download()
    imdb_url:          str = ""               # full episode page URL

    def __str__(self) -> str:
        return f"{self.episode_code} · {self.title}  [{self.rating}]"

    def to_dict(self) -> dict:
        return asdict(self)


# ─── SeriesMetadata ───────────────────────────────────────────────────────────

@dataclass
class SeriesMetadata:
    """
    Header-level information scraped from the IMDBx title hero section.

    All fields except `series_name` and `title_id` are Optional — IMDBx
    may not display every field for every title.
    """

    title_id:    str                     # "tt7441658"
    series_name: str                     # "Black Clover"

    # Inline hero list (TV Series · 2017–2021 · TV-PG · 24m)
    type:             Optional[str] = None   # "TV Series" | "Movie" | …
    years:            Optional[str] = None   # "2017–2021"
    content_rating:   Optional[str] = None   # "TV-PG" | "PG-13" | …
    episode_duration: Optional[str] = None   # "24m" | "1h 30m" | …

    # Ratings
    imdb_rating:  Optional[str] = None   # "8.2/10"
    rating_count: Optional[str] = None   # "47K"
    popularity:   Optional[str] = None   # "529"

    # Interest / genre tags
    tags: list[str] = field(default_factory=list)
    # e.g. ["Japanese", "Anime", "Action", "Adventure", …]

    def __str__(self) -> str:
        parts = [self.series_name]
        if self.years:
            parts.append(self.years)
        if self.type:
            parts.append(self.type)
        if self.imdb_rating:
            votes = f" ({self.rating_count})" if self.rating_count else ""
            parts.append(f"★ {self.imdb_rating}{votes}")
        return "  ·  ".join(parts)

    def to_dict(self) -> dict:
        return asdict(self)


# ─── TitleInfo ────────────────────────────────────────────────────────────────

@dataclass
class TitleInfo:
    """
    Everything scraped for a single IMDBx title.

    Attributes
    ----------
    meta:
        Series-level metadata (name, rating, tags, etc.)
    seasons:
        Dict mapping season number → list of Episode objects.
        Keys are always integers, sorted ascending.

    Convenience helpers
    -------------------
    .all_episodes()         → flat list of every Episode across all seasons
    .get_episode(s, e)      → a specific Episode or None
    .to_dict()              → plain dict (JSON-serialisable)
    .save(path)             → write JSON to disk
    """

    meta:    SeriesMetadata
    seasons: dict[int, list[Episode]] = field(default_factory=dict)

    # ── Convenience ───────────────────────────────────────────────────────────

    def all_episodes(self) -> list[Episode]:
        """Return every episode in season order."""
        result = []
        for eps in self.seasons.values():
            result.extend(eps)
        return result

    def get_episode(self, season: int, episode: int) -> Optional[Episode]:
        """Return the Episode for S<season>E<episode>, or None if not found."""
        for ep in self.seasons.get(season, []):
            if ep.episode == episode:
                return ep
        return None

    def episode_count(self) -> int:
        return sum(len(v) for v in self.seasons.values())

    def season_count(self) -> int:
        return len(self.seasons)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            **self.meta.to_dict(),
            "seasons": {
                str(k): [ep.to_dict() for ep in v]
                for k, v in self.seasons.items()
            },
        }

    def save(self, path: str | Path) -> Path:
        """Serialise to JSON and write to *path*. Returns the resolved Path."""
        p = Path(path)
        p.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return p

    # ── Dunder helpers ────────────────────────────────────────────────────────

    def __str__(self) -> str:
        return (
            f"{self.meta.series_name}  [{self.meta.title_id}]  "
            f"— {self.season_count()} seasons, {self.episode_count()} episodes"
        )

    def __repr__(self) -> str:
        return f"TitleInfo(title_id={self.meta.title_id!r}, seasons={list(self.seasons.keys())})"

    def __iter__(self):
        """Iterate over (season_number, episodes) pairs."""
        return iter(self.seasons.items())
