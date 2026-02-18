"""
imdbx._browser
=============
Layer 2: Playwright browser pool.

Responsibilities
----------------
• Launch a shared headless Chromium instance
• Render each IMDBx season page with full JavaScript execution
• Detect and click "Show more" / "N more" buttons to reveal hidden episodes
• Return a BeautifulSoup for each season page

Load-more detection (4 strategies, zero hardcoded class names)
--------------------------------------------------------------
IMDBx's "Show more" is an <a> tag that navigates to a /search/title/ page —
we deliberately skip those.  Genuine inline loaders ("N more", "load more",
"see all") are <button> or non-navigating <a> elements.

Strategy 1 – <button> whose inner text matches _INLINE_MORE
Strategy 2 – <a> without a navigating href whose text matches _INLINE_MORE
Strategy 3 – ancestor data-testid contains see-more / load-more / expand
Strategy 4 – aria-label contains "more" or "see all"
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import sys

from bs4 import BeautifulSoup
from playwright.async_api import (
    async_playwright,
    Browser,
    Page,
    TimeoutError as PWTimeout,
)

from ._log import dbg, c, C


# ─── Chromium auto-installer ──────────────────────────────────────────────────

_CHROMIUM_READY: bool = False   # guard: checked once per process, then skipped


def _chromium_exe() -> str | None:
    """
    Return the path to Playwright's Chromium executable without launching
    any subprocess.  Reads Playwright's internal browser registry directly.
    Returns None if the registry can't be read or the path doesn't exist.
    """
    try:
        from playwright._impl._driver import compute_driver_executable
        from pathlib import Path
        import json

        # Playwright stores browser locations in a JSON registry next to its driver
        driver = Path(compute_driver_executable()[0]).parent
        registry = driver / "package" / "browsers.json"
        if not registry.exists():
            # fallback location in some versions
            registry = driver.parent / "browsers.json"
        if not registry.exists():
            return None

        data     = json.loads(registry.read_text())
        browsers = data.get("browsers", [])
        revision = next(
            (b["revision"] for b in browsers if b.get("name") == "chromium"), None
        )
        if not revision:
            return None

        # Playwright caches browsers under ~/.cache/ms-playwright/ (Linux/Mac)
        # or %LOCALAPPDATA%\ms-playwright\ (Windows)
        import platform, os
        if platform.system() == "Windows":
            base = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        elif platform.system() == "Darwin":
            base = Path.home() / "Library" / "Caches" / "ms-playwright"
        else:
            base = Path.home() / ".cache" / "ms-playwright"

        # Walk the chromium-NNNN folder for the actual executable
        candidates = [
            base / f"chromium-{revision}" / "chrome-linux"  / "chrome",
            base / f"chromium-{revision}" / "chrome-mac"    / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
            base / f"chromium-{revision}" / "chrome-win"    / "chrome.exe",
        ]
        for p in candidates:
            if p.exists():
                return str(p)
    except Exception:
        pass
    return None


def ensure_chromium() -> None:
    """
    Make sure Playwright's Chromium binary is present.

    • If it already exists  → returns instantly (no subprocess, no I/O).
    • If it is missing      → runs `playwright install chromium`, streaming
                              progress to stdout, then continues seamlessly.

    Called automatically before every browser launch.
    Users never need to run `playwright install chromium` manually.
    """
    global _CHROMIUM_READY
    if _CHROMIUM_READY:
        return   # fast path — already verified this process

    if _chromium_exe() is not None:
        _CHROMIUM_READY = True
        return   # binary present — nothing to do

    # Binary missing — install it, streaming output so the user sees progress
    print(
        f"{c('◈  Chromium not found — downloading now (once only)…', C.BYELLOW, C.BOLD)}"
    )
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False,
        # stdout/stderr inherit from parent so download progress streams live
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Chromium auto-install failed.  "
            "Run manually:  playwright install chromium"
        )

    print(f"{c('✓  Chromium ready.', C.BGREEN, C.BOLD)}")
    _CHROMIUM_READY = True


# Inline load-more patterns only — "show more" is intentionally excluded
# because on IMDBx it navigates to a /search/title/ rating-sorted page.
_INLINE_MORE = re.compile(r"\d+\s+more|see\s+all|load\s+more", re.I)


# ─── Navigation guard ─────────────────────────────────────────────────────────

def _is_navigating_href(href: str | None) -> bool:
    """True if clicking this href would leave the current page."""
    if not href:
        return False
    h = href.strip()
    if not h or h.startswith("#") or h.lower().startswith("javascript:"):
        return False
    return True


# ─── Load-more finder ─────────────────────────────────────────────────────────

async def _find_loadmore(page: Page):
    """
    Return a Playwright Locator for a genuine inline load-more element, or None.
    Checks <button> and <a> in four strategies (see module docstring).
    """

    # Strategy 1: <button> — always safe, no href risk
    loc = page.locator("button:visible")
    for i in range(await loc.count()):
        el = loc.nth(i)
        try:
            if _INLINE_MORE.search((await el.inner_text()).strip()):
                if await el.is_enabled():
                    return el
        except Exception:
            continue

    # Strategy 2: <a> without a navigating href
    loc = page.locator("a:visible")
    for i in range(await loc.count()):
        el = loc.nth(i)
        try:
            href = await el.get_attribute("href") or ""
            if _is_navigating_href(href):
                continue
            if _INLINE_MORE.search((await el.inner_text()).strip()):
                if (await el.get_attribute("aria-disabled")) != "true":
                    return el
        except Exception:
            continue

    # Strategy 3: ancestor data-testid
    for frag in ("see-more", "load-more", "expand"):
        for tag in ("button", "a"):
            loc = page.locator(
                f"[data-testid*='{frag}'] {tag}:visible, "
                f"{tag}[data-testid*='{frag}']:visible"
            )
            if await loc.count() > 0:
                el = loc.first
                try:
                    href = await el.get_attribute("href") or ""
                    if tag == "a" and _is_navigating_href(href):
                        continue
                    if (await el.get_attribute("aria-disabled")) != "true":
                        return el
                except Exception:
                    continue

    # Strategy 4: aria-label
    for tag in ("button", "a"):
        loc = page.locator(
            f"{tag}[aria-label*='more' i]:visible, "
            f"{tag}[aria-label*='see all' i]:visible"
        )
        for i in range(await loc.count()):
            el = loc.nth(i)
            try:
                href = await el.get_attribute("href") or ""
                if tag == "a" and _is_navigating_href(href):
                    continue
                if (await el.get_attribute("aria-disabled")) != "true":
                    return el
            except Exception:
                continue

    return None


# ─── Episode expander ─────────────────────────────────────────────────────────

async def _expand_episodes(page: Page, season_num: int, episode_url: str) -> None:
    """
    Click every genuine inline load-more element until none remain.

    After each click:
      1. Verifies the URL has NOT changed (still on the episode list page)
      2. Waits for new <article> cards to appear in the DOM
    """
    click_count = 0
    while True:
        el = await _find_loadmore(page)
        if el is None:
            break

        before_count = await page.locator("article").count()
        before_url   = page.url

        try:
            label = (await el.inner_text()).strip().replace("\n", " ")
            await el.scroll_into_view_if_needed()
            await el.click()
            click_count += 1
            dbg(f"     {c('↳', C.BCYAN)} S{c(season_num, C.BYELLOW)}: "
                f"{c(f'clicked load-more #{click_count}', C.BBLUE)} — {c(repr(label), C.DIM)}")

            await asyncio.sleep(0.4)

            if page.url != before_url:
                dbg(c(f"     ⚠  S{season_num}: navigation detected, going back.", C.YELLOW))
                await page.goto(episode_url, wait_until="domcontentloaded", timeout=30_000)
                await page.wait_for_selector("article", timeout=15_000)
                break

            try:
                await page.wait_for_function(
                    f"document.querySelectorAll('article').length > {before_count}",
                    timeout=12_000,
                )
            except PWTimeout:
                await page.wait_for_load_state("networkidle", timeout=8_000)

            await asyncio.sleep(0.3)

        except PWTimeout:
            break
        except Exception as exc:
            dbg(c(f"     ✗  S{season_num}: click error — {exc}", C.RED))
            break

    after = await page.locator("article").count()
    if click_count:
        dbg(f"     {c('✓', C.BGREEN)}  S{c(season_num, C.BYELLOW)}: "
            f"{c(click_count, C.BWHITE)} click(s), {c(after, C.BWHITE)} episodes visible.")
    else:
        dbg(f"     ✓  S{season_num}: no inline load-more — {after} episodes visible.")


# ─── Single-season page fetch ─────────────────────────────────────────────────

async def _fetch_season_page(
    title_id: str,
    season_num: int,
    browser: Browser,
    base_url: str,
    retries: int = 3,
) -> tuple[int, BeautifulSoup | None]:
    """
    Open an isolated browser context, navigate to the season episode list,
    expand all hidden episodes, return (season_num, soup).
    """
    from ._http import HEADERS

    url = f"{base_url}/title/{title_id}/episodes/?season={season_num}"

    for attempt in range(1, retries + 1):
        context = await browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="en-US",
            viewport={"width": 1280, "height": 900},
            extra_http_headers={"Accept-Language": HEADERS["Accept-Language"]},
        )
        await context.route(
            re.compile(r"\.(woff2?|ttf|otf)$|doubleclick|google-analytics"),
            lambda r: r.abort(),
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_selector("article", timeout=15_000)
            await _expand_episodes(page, season_num, url)
            html = await page.content()
            return season_num, BeautifulSoup(html, "html.parser")

        except PWTimeout:
            dbg(c(f"  ⚠  S{season_num} attempt {attempt}/{retries} timed out.", C.YELLOW))
        except Exception as exc:
            dbg(c(f"  ⚠  S{season_num} attempt {attempt}/{retries} — {exc}", C.YELLOW))
        finally:
            await page.close()
            await context.close()

        if attempt < retries:
            await asyncio.sleep(2 * attempt)

    return season_num, None


# ─── Concurrent season scraper ────────────────────────────────────────────────

async def fetch_seasons_async(
    title_id: str,
    season_nums: list[int],
    pool_size: int,
    base_url: str,
) -> list[tuple[int, BeautifulSoup | None]]:
    """
    Fetch multiple season pages concurrently using a Playwright browser pool.
    Returns a list of (season_num, soup) tuples.
    """
    results: list[tuple[int, BeautifulSoup | None]] = []
    sem = asyncio.Semaphore(pool_size)

    ensure_chromium()   # auto-install Chromium if missing (no-op if already present)

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=True)

        async def fetch_one(n: int):
            async with sem:
                pair = await _fetch_season_page(title_id, n, browser, base_url)
                results.append(pair)

        await asyncio.gather(*[fetch_one(n) for n in season_nums])
        await browser.close()

    return results
