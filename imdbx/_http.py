"""
imdbx._http
==========
Layer 1: niquests HTTP connection pool.

Responsibilities
----------------
• One shared niquests.Session with persistent TCP keep-alive pools
• Retry-with-backoff for all GETs
• Concurrent image downloading via niquests.AsyncSession
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse
from typing import TYPE_CHECKING

import niquests
from niquests import AsyncSession
from niquests.adapters import HTTPAdapter
from bs4 import BeautifulSoup

from ._log import dbg, c, C

if TYPE_CHECKING:
    pass


# ─── Shared headers ───────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}


# ─── Session factory ──────────────────────────────────────────────────────────

def make_session(pool_size: int = 8) -> niquests.Session:
    """
    Return a niquests Session backed by a persistent connection pool.

    pool_connections  – distinct host pools to maintain (IMDBx + CDN = 2)
    pool_maxsize      – max idle keep-alive sockets per host
    """
    session = niquests.Session()
    adapter = HTTPAdapter(pool_connections=2, pool_maxsize=pool_size)
    session.mount("https://", adapter)
    session.mount("http://",  adapter)
    session.headers.update(HEADERS)
    return session


# ─── Fetch helpers ────────────────────────────────────────────────────────────

def http_fetch(
    url: str,
    session: niquests.Session,
    retries: int = 3,
) -> BeautifulSoup | None:
    """
    GET *url* through the shared connection pool.
    Returns a BeautifulSoup object on success, None after all retries fail.
    """
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except niquests.exceptions.RequestException as exc:
            dbg(c(f"  ⚠  HTTP ({attempt}/{retries}) {url} — {exc}", C.YELLOW))
            if attempt < retries:
                time.sleep(1.5 * attempt)
    return None


# ─── Image downloading ────────────────────────────────────────────────────────

def _ext_from_url(url: str) -> str:
    """Guess file extension from a CDN URL path, defaulting to .jpg."""
    path = urlparse(url).path
    _, ext = os.path.splitext(path)
    return ext.lower() if ext.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else ".jpg"


async def _download_one(url: str, dest: Path, session: AsyncSession, retries: int = 3) -> bool:
    """Download a single image to *dest*. Returns True on success."""
    if dest.exists():
        return True   # resume-safe
    for attempt in range(1, retries + 1):
        try:
            resp = await session.get(url, timeout=20)
            resp.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(resp.content)
            return True
        except Exception as exc:
            if attempt < retries:
                await asyncio.sleep(1.5 * attempt)
            else:
                dbg(f"  [!] Image download failed: {dest.name} — {exc}")
    return False


async def _download_all(jobs: list[tuple[str, Path]], pool_size: int) -> None:
    """Download all images concurrently, honouring *pool_size* in-flight limit."""
    sem = asyncio.Semaphore(pool_size)
    async with AsyncSession(headers={**HEADERS, "Accept": "image/*"}) as session:
        async def bounded(url: str, dest: Path):
            async with sem:
                ok = await _download_one(url, dest, session)
                status = c("✓", C.BGREEN) if ok else c("✗", C.RED)
                dbg(f"     {status}  {c(dest.name, C.DIM)}")

        await asyncio.gather(*[bounded(url, dest) for url, dest in jobs])


def download_images(
    title_info,          # TitleInfo — imported lazily to avoid circular deps
    images_dir: Path,
    pool_size: int = 8,
) -> None:
    """
    Download all episode cover images referenced in *title_info* and update
    each Episode's `cover_image_local` field with the local relative path.

    Files are saved as:  <images_dir>/<title_id>/S<s>E<e>.<ext>
    Already-downloaded files are skipped (safe to re-run).
    """
    title_id = title_info.meta.title_id
    base = images_dir / title_id
    jobs: list[tuple[str, Path]] = []

    for season_num, episodes in title_info.seasons.items():
        for ep in episodes:
            url = ep.cover_image
            if not url:
                ep.cover_image_local = None
                continue
            ext      = _ext_from_url(url)
            filename = f"S{ep.season}E{ep.episode}{ext}"
            dest     = base / filename
            ep.cover_image_local = str(dest)
            jobs.append((url, dest))

    if not jobs:
        dbg("  [!] No cover image URLs found — nothing to download.")
        return

    total = len(jobs)
    print(f"\n{c('▣  Downloading', C.BCYAN, C.BOLD)} {c(total, C.BYELLOW, C.BOLD)} cover image(s) → {c(str(base), C.DIM)}/")
    asyncio.run(_download_all(jobs, pool_size))
    saved = sum(1 for _, d in jobs if d.exists())
    print(f"\n  {c('✓', C.BGREEN, C.BOLD)}  {c(f'{saved}/{total} images saved', C.BWHITE, C.BOLD)}")
