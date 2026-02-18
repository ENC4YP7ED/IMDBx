"""
imdbx._display
=============
Rich terminal output helpers.

`print_title(title_info)`  — pretty-prints a full TitleInfo to stdout.
`print_episode(episode)`   — prints a single Episode card.

These are purely cosmetic — no logic lives here.
"""

from __future__ import annotations

import re

from .models import Episode, TitleInfo
from ._log import c, C


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _stars(rating_str: str, out_of: int = 10) -> str:
    """Convert '7.6/10' → coloured star bar."""
    m = re.match(r"([\d.]+)", rating_str or "")
    if not m:
        return c("─── no rating ───", C.DIM)
    val    = float(m.group(1))
    filled = round(val)
    empty  = out_of - filled
    color  = C.BGREEN if val >= 8 else (C.BYELLOW if val >= 6 else C.RED)
    return c("★" * filled, color) + c("☆" * empty, C.DIM)


def _wrap(text: str, width: int = 64) -> list[str]:
    """Word-wrap *text* to lines of at most *width* chars."""
    if not text:
        return [""]
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines or [""]


def _box_row(content: str, width: int, color=C.BCYAN) -> None:
    """Print a single ║ … ║ row, padding content to *width*."""
    # Strip ANSI for length calculation
    raw_len = len(re.sub(r"\033\[[^m]*m", "", content))
    pad = width - 2 - raw_len
    print(c("║", color) + content + " " * max(pad, 0) + c("║", color))


# ─── Public helpers ───────────────────────────────────────────────────────────

def print_episode(ep: Episode) -> None:
    """Print a compact summary card for a single Episode."""
    W = 72
    print(c("  │ ", C.BCYAN) + c(f"{ep.episode_code:<8}", C.BCYAN, C.BOLD) + " " + c(ep.title, C.BWHITE, C.BOLD))

    # Rating
    rm = re.match(r"([\d.]+)/10(?:\s*\(([^)]+)\))?", ep.rating)
    rnum   = rm.group(1) if rm else "?"
    rvotes = rm.group(2) if (rm and rm.group(2)) else ""
    print(
        c("  │   ", C.BCYAN) +
        _stars(ep.rating) + "  " +
        c(f"{rnum}/10", C.BYELLOW, C.BOLD) +
        (" " + c(f"({rvotes})", C.DIM) if rvotes else "")
    )

    # Description (max 2 wrapped lines)
    desc_lines = _wrap(ep.description, width=W - 8)[:2]
    for i, line in enumerate(desc_lines):
        suffix = c(" …", C.DIM) if (i == 1 and len(_wrap(ep.description, W - 8)) > 2) else ""
        print(c("  │   ", C.BCYAN) + c(line, C.DIM) + suffix)

    if ep.cover_image_local:
        print(c("  │   ", C.BCYAN) + c("▸ " + ep.cover_image_local, C.DIM))

    print(c("  │", C.BCYAN))


def print_title(info: TitleInfo) -> None:
    """Pretty-print a full TitleInfo with header box and per-season blocks."""
    meta     = info.meta
    seasons  = info.seasons
    total_ep = info.episode_count()
    W        = 72

    # ── Header box ────────────────────────────────────────────────────────────
    print()
    print(c("╔" + "═" * (W - 2) + "╗", C.BCYAN, C.BOLD))

    title_content = c(f"  {meta.series_name}  ·  {meta.title_id}", C.BWHITE, C.BOLD)
    _box_row(title_content, W)

    # Type / years / content rating / duration
    meta_parts = [v for k in ("type", "years", "content_rating", "episode_duration")
                  if (v := getattr(meta, k, None))]
    if meta_parts:
        _box_row(c("  " + "  ·  ".join(meta_parts), C.DIM), W)

    # Rating row
    if meta.imdb_rating:
        votes_part = f"  ({meta.rating_count} votes)" if meta.rating_count else ""
        pop_part   = f"   Popularity: #{meta.popularity}" if meta.popularity else ""
        _box_row(
            c("  ★  ", C.BYELLOW) + c(f"{meta.imdb_rating}{votes_part}{pop_part}", C.BYELLOW),
            W,
        )

    # Tags row
    if meta.tags:
        tag_str = "  " + " · ".join(meta.tags)
        if len(tag_str) > W - 2:
            tag_str = tag_str[:W - 5] + "..."
        _box_row(c(tag_str, C.BCYAN), W)

    # Seasons / episodes count
    raw_stats = f"  Seasons: {len(seasons)}   Episodes: {total_ep}"
    _box_row(
        "  " + f"Seasons: {c(len(seasons), C.BYELLOW, C.BOLD)}   Episodes: {c(total_ep, C.BYELLOW, C.BOLD)}",
        W,
    )
    print(c("╚" + "═" * (W - 2) + "╝", C.BCYAN, C.BOLD))

    # ── Season blocks ─────────────────────────────────────────────────────────
    for season_num, episodes in seasons.items():
        print()
        s_label = f" SEASON {season_num} "
        s_ep    = f" {len(episodes)} episodes "
        pad     = W - 4 - len(s_label) - len(s_ep)
        print(
            c("  ┌", C.BCYAN) +
            c(s_label, C.BG_BLUE, C.BWHITE, C.BOLD) +
            c("─" * max(pad, 0), C.BCYAN) +
            c(s_ep, C.DIM) +
            c("┐", C.BCYAN)
        )
        for ep in episodes:
            print_episode(ep)
        print(c("  └" + "─" * (W - 4) + "┘", C.BCYAN))

    print()
