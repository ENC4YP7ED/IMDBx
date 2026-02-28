"""
imdbx.cli
=========
Command-line interface for IMDBx.  Installed as the ``imdbx`` command.

The CLI is the primary way to use IMDBx without writing Python.  It covers
every capability of the Python API: full-series scraping, single-season and
single-episode extraction, metadata-only fetches, JSON save/load, cover-image
downloading, and both unit-test and live smoke-test modes.

Usage
-----
    imdbx tt7441658
    imdbx tt7441658 --seasons 1 2
    imdbx tt7441658 --output black_clover.json
    imdbx tt7441658 --download-images
    imdbx tt7441658 --images-dir ~/my_images
    imdbx tt7441658 --pool-size 8 --debug
    imdbx tt7441658 --meta-only          # fast: metadata only, no episodes
    imdbx --load black_clover.json       # pretty-print an existing JSON file
    imdbx --test                         # run the full unit-test suite
    imdbx --test tt7441658               # live smoke-test against a real title
"""

from __future__ import annotations

import argparse
import sys

from . import title, metadata, load, set_debug
from ._log import c, C
from ._display import print_title


# ─────────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _run_tests() -> None:
    """Run the full pytest suite and exit with pytest's return code."""
    try:
        import pytest
    except ImportError:
        print(
            f"{c('✗  pytest not found.', C.BRED, C.BOLD)}  "
            f"Install dev extras:  {c('pip install \"IMDBx[dev]\"', C.BCYAN)}",
            file=sys.stderr,
        )
        sys.exit(1)

    from pathlib import Path

    pkg_root  = Path(__file__).parent.parent
    tests_dir = pkg_root / "tests"

    if not tests_dir.exists() or not (tests_dir / "test_models_episode_dataclass.py").exists():
        print(
            f"{c('✗  IMDBx tests not found.', C.BRED, C.BOLD)}  "
            f"Run from a source checkout:  "
            f"{c('git clone https://github.com/ENC4YP7ED/IMDBx && pip install -e \".[dev]\"', C.BCYAN)}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\n{c('▸  Running test suite', C.BWHITE, C.BOLD)} → {c(str(tests_dir), C.BCYAN)}\n")
    ret = pytest.main([str(tests_dir), "-v", "--tb=short"])
    sys.exit(ret)


def _run_smoke_test(tt_id: str) -> None:
    """Run a live smoke test against a real IMDb title ID."""
    import traceback

    print(f"\n{c('▸  Smoke test', C.BWHITE, C.BOLD)}: {c(tt_id, C.BCYAN)}\n")
    steps: list[tuple[str, bool, str]] = []

    def check(label: str, fn):
        try:
            result = fn()
            steps.append((label, True, repr(result)[:120]))
            return result
        except Exception:
            steps.append((label, False, traceback.format_exc(limit=3)))
            return None

    # Step 1 — metadata (no browser, fast)
    m = check("metadata()", lambda: metadata(tt_id))

    # Step 2 — verify key fields
    if m is not None:
        check(
            "meta.series_name non-empty",
            lambda: m.series_name if m.series_name
                    else (_ for _ in ()).throw(ValueError("series_name is empty")),  # type: ignore[arg-type]
        )
        check("meta.to_dict() serialisable", lambda: m.to_dict())

    # Step 3 — single season (browser required)
    from . import season as _season
    eps = check(f"season({tt_id!r}, 1)", lambda: _season(tt_id, 1))

    if eps is not None:
        check(
            "at least 1 episode returned",
            lambda: eps if eps
                    else (_ for _ in ()).throw(ValueError("no episodes")),  # type: ignore[arg-type]
        )
        if eps:
            ep = eps[0]
            check(
                "episode.title non-empty",
                lambda: ep.title if ep.title
                        else (_ for _ in ()).throw(ValueError("title empty")),  # type: ignore[arg-type]
            )
            check(
                "episode.episode_code non-empty",
                lambda: ep.episode_code if ep.episode_code
                        else (_ for _ in ()).throw(ValueError("code empty")),  # type: ignore[arg-type]
            )

    # ── Print results ─────────────────────────────────────────────────────────
    passed = sum(1 for _, ok, _ in steps if ok)
    failed = sum(1 for _, ok, _ in steps if not ok)

    for label, ok, detail in steps:
        icon   = c("✓", C.BGREEN, C.BOLD) if ok else c("✗", C.BRED, C.BOLD)
        colour = C.GREEN if ok else C.RED
        print(f"  {icon}  {c(label, colour)}")
        if not ok:
            for line in detail.splitlines():
                print(f"       {c(line, C.DIM)}")

    print()
    summary_colour = C.BGREEN if failed == 0 else C.BRED
    print(c(f"  {passed} passed, {failed} failed", summary_colour, C.BOLD))
    print()
    sys.exit(0 if failed == 0 else 1)


# ─────────────────────────────────────────────────────────────────────────────
#  main()
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="imdbx",
        description=(
            f"{c('IMDBx Scraper', C.BWHITE, C.BOLD)}\n"
            f"{c('Scrape episode titles, ratings, descriptions and cover art for any IMDb TV series.', C.DIM)}\n\n"
            f"{c('Requirements:', C.BYELLOW)}  "
            f"pip install IMDBx  &&  playwright install chromium\n\n"
            f"{c('Examples:', C.BYELLOW)}\n"
            f"  imdbx tt7441658                     {c('# Black Clover, all seasons', C.DIM)}\n"
            f"  imdbx tt0903747                     {c('# Breaking Bad', C.DIM)}\n"
            f"  imdbx tt7441658 -s 1 2              {c('# specific seasons only', C.DIM)}\n"
            f"  imdbx tt7441658 -o out.json         {c('# save results to a JSON file', C.DIM)}\n"
            f"  imdbx tt7441658 --download-images   {c('# also download cover art', C.DIM)}\n"
            f"  imdbx tt7441658 --meta-only         {c('# series metadata only, no episodes', C.DIM)}\n"
            f"  imdbx --load out.json               {c('# display a previously saved file', C.DIM)}\n"
            f"  imdbx --test                        {c('# run the full unit-test suite', C.DIM)}\n"
            f"  imdbx --test tt7441658              {c('# live smoke-test a real title', C.DIM)}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # ── Positional ────────────────────────────────────────────────────────────
    parser.add_argument(
        "title_id",
        nargs="?",
        default=None,
        metavar="TITLE_ID",
        help=(
            "The IMDb title ID to scrape — the 'tt…' code from any IMDb URL.  "
            "Example: tt7441658 for Black Clover, tt0903747 for Breaking Bad.  "
            "Required unless --load or --test is used."
        ),
    )

    # ── Season / episode filtering ────────────────────────────────────────────
    parser.add_argument(
        "-s", "--seasons",
        type=int,
        nargs="+",
        default=None,
        metavar="N",
        help=(
            "Restrict scraping to one or more specific season numbers.  "
            "Pass multiple values separated by spaces.  "
            "Example: -s 1 2 3 scrapes seasons 1, 2 and 3 only.  "
            "By default all available seasons are scraped."
        ),
    )

    # ── Output ────────────────────────────────────────────────────────────────
    parser.add_argument(
        "-o", "--output",
        default=None,
        metavar="FILE",
        help=(
            "Save the scraped results to this JSON file.  "
            "The file is written in IMDBx's standard format and can be reloaded "
            "later with --load.  "
            "Example: --output black_clover.json"
        ),
    )

    # ── Concurrency ───────────────────────────────────────────────────────────
    parser.add_argument(
        "-p", "--pool-size",
        type=int,
        default=4,
        dest="pool_size",
        metavar="N",
        help=(
            "Maximum number of concurrent Playwright browser tabs and image "
            "download connections.  "
            "Higher values finish faster at the cost of more RAM and CPU.  "
            "Recommended range: 2–16.  Default: 4."
        ),
    )

    # ── Images ────────────────────────────────────────────────────────────────
    parser.add_argument(
        "--download-images",
        action="store_true",
        dest="download_images",
        help=(
            "Download episode cover images to ./images/<title_id>/ alongside "
            "the scraped data.  "
            "Image URLs are always stored in the output regardless of this flag; "
            "this flag controls whether the actual files are fetched.  "
            "See also --images-dir to choose a custom directory."
        ),
    )

    parser.add_argument(
        "--images-dir",
        default=None,
        dest="images_dir",
        metavar="DIR",
        help=(
            "Save episode cover images to this directory instead of the default "
            "./images/<title_id>/ location.  "
            "Setting this flag automatically enables image downloading "
            "(you do not need to also pass --download-images).  "
            "Supports ~ expansion.  Example: --images-dir ~/Downloads/covers"
        ),
    )

    # ── Metadata-only mode ────────────────────────────────────────────────────
    parser.add_argument(
        "--meta-only",
        action="store_true",
        dest="meta_only",
        help=(
            "Fetch and display series-level metadata only — title, year range, "
            "content rating, IMDBx rating, genres, and popularity score.  "
            "Skips all episode scraping and does not launch a browser, so it "
            "completes in a few seconds.  "
            "Useful for a quick overview or scripting checks."
        ),
    )

    # ── Load saved file ───────────────────────────────────────────────────────
    parser.add_argument(
        "--load",
        default=None,
        metavar="FILE",
        help=(
            "Load and pretty-print a JSON file that was previously saved with "
            "--output.  "
            "No network requests or browser are needed — this works entirely "
            "offline.  "
            "Example: --load black_clover.json"
        ),
    )

    # ── Test mode ─────────────────────────────────────────────────────────────
    parser.add_argument(
        "--test",
        nargs="?",
        const="",
        default=None,
        metavar="TITLE_ID",
        help=(
            "Run tests.  Two modes depending on whether a TITLE_ID is supplied:\n"
            "  --test              Run the full offline unit-test suite using pytest.  "
            "Requires the  extras (pip install IMDBx).  "
            "Exits with pytest's return code (0 = all passed).\n"
            "  --test tt7441658    Run a live end-to-end smoke test against the given "
            "IMDb title.  Fetches real metadata and the first season, checks that "
            "key fields are populated, and prints a coloured pass/fail summary.  "
            "Requires a network connection and Playwright/Chromium."
        ),
    )

    # ── Debug ─────────────────────────────────────────────────────────────────
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        default=False,
        help=(
            "Enable verbose debug output.  "
            "Prints HTTP requests, Playwright browser events, parse decisions, "
            "and timing information to stderr.  "
            "Useful for diagnosing scraping failures or unexpected results."
        ),
    )

    args = parser.parse_args()

    if args.debug:
        set_debug(True)

    # ── Test mode — one arg, two behaviours ──────────────────────────────────
    #   imdbx --test              →  args.test == ""          →  run pytest suite
    #   imdbx --test tt7441658   →  args.test == "tt7441658"  →  live smoke test
    if args.test is not None:
        if args.test == "":
            _run_tests()
        else:
            _run_smoke_test(args.test)
        return  # both helpers call sys.exit; this is a safety net

    # ── Load mode ─────────────────────────────────────────────────────────────
    if args.load:
        info = load(args.load)
        print_title(info)
        return

    # ── Scrape mode ───────────────────────────────────────────────────────────
    if not args.title_id:
        parser.print_help()
        sys.exit(1)

    if args.meta_only:
        m = metadata(args.title_id)
        print(f"\n{m}\n")
        if m.tags:
            print(f"Tags: {', '.join(m.tags)}")
        return

    info = title(
        args.title_id,
        seasons         = args.seasons,
        pool_size       = args.pool_size,
        images_dir      = args.images_dir,
        download_images = args.download_images,
    )

    if args.output:
        saved = info.save(args.output)
        print(f"\n{c('▸  Saved', C.BGREEN, C.BOLD)} → {c(str(saved), C.BCYAN)}")

    print_title(info)


if __name__ == "__main__":
    main()
