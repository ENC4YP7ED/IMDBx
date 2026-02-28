# IMDBx

[![PyPI](https://img.shields.io/pypi/v/IMDBx)](https://pypi.org/project/IMDBx/)
[![Python](https://img.shields.io/pypi/pyversions/IMDBx)](https://pypi.org/project/IMDBx/)
[![CI](https://github.com/ENC4YP7ED/IMDBx/actions/workflows/test.yml/badge.svg)](https://github.com/ENC4YP7ED/IMDBx/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

IMDBx - Titles, ratings, air dates, descriptions and cover art across every episode of any IMDb TV series.

---

## Install

```bash
pip install IMDBx
```

Chromium is downloaded automatically the first time you run a scrape — no extra setup needed.

For development (includes pytest, ruff, coverage):

```bash
pip install "IMDBx[dev]"
```

---

## Quick start

```python
from imdbx import title

t = title("tt7441658")          # Black Clover, all seasons
print(t)                         # Black Clover [tt7441658] — 4 seasons, 170 episodes

for season_num, episodes in t:
    for ep in episodes:
        print(ep)                # S1.E1 · Asta and Yuno  [7.6/10 (1.6K)]
```

---

## Python API

```python
from imdbx import title, season, episode, metadata, load
```

### `title()` — full series

```python
t = title("tt7441658")
t = title("tt7441658", seasons=[1, 2])          # specific seasons only
t = title("tt7441658", download_images=True)    # also save cover art
t = title("tt7441658", pool_size=8)             # more concurrency

print(t.meta.series_name)        # "Black Clover"
print(t.meta.imdb_rating)        # "8.2/10"
print(t.meta.tags)               # ["Anime", "Action", "Adventure", …]
print(t.meta.years)              # "2017–2021"
print(t.meta.content_rating)     # "TV-PG"

all_eps = t.all_episodes()       # flat list of every Episode
ep      = t.get_episode(1, 1)    # Episode S1E1
t.save("black_clover.json")      # dump to JSON
```

### `season()` — single season

```python
eps = season("tt7441658", 1)     # list[Episode] for season 1

for ep in eps:
    print(ep.title, ep.rating)
```

### `episode()` — single episode

```python
ep = episode("tt7441658", 1, 1)  # Season 1, Episode 1

print(ep.episode_code)           # "S1.E1"
print(ep.title)                  # "Asta and Yuno"
print(ep.rating)                 # "7.6/10 (1.6K)"
print(ep.air_date)               # "Tue, Oct 3, 2017"
print(ep.description)            # plot summary
print(ep.cover_image)            # CDN URL
print(ep.imdb_url)               # full IMDBx page URL
```

### `metadata()` — series info only (fast, no browser)

```python
m = metadata("tt7441658")

print(m.series_name)             # "Black Clover"
print(m.type)                    # "TV Series"
print(m.years)                   # "2017–2021"
print(m.content_rating)          # "TV-PG"
print(m.episode_duration)        # "24m"
print(m.imdb_rating)             # "8.2/10"
print(m.rating_count)            # "47K"
print(m.popularity)              # "529"
print(m.tags)                    # ["Japanese", "Anime", "Action", …]
```

### `load()` — reload a saved JSON file

```python
t = load("black_clover.json")
print(t.meta.series_name)
```

---

## Data classes

### `Episode`

| Field | Type | Description |
|---|---|---|
| `episode_code` | `str` | Short code, e.g. `"S1.E1"` |
| `title` | `str` | Episode title |
| `season` | `int` | Season number (1-indexed) |
| `episode` | `int` | Episode number within the season (1-indexed) |
| `air_date` | `str` | Original air date, e.g. `"Tue, Oct 3, 2017"` |
| `description` | `str` | Plot summary |
| `rating` | `str` | IMDBx rating, e.g. `"7.6/10 (1.6K)"` |
| `cover_image` | `str \| None` | CDN URL of the episode thumbnail |
| `cover_image_local` | `str \| None` | Local file path after `--download-images` |
| `imdb_url` | `str` | Full IMDBx episode page URL |

### `SeriesMetadata`

| Field | Type | Description |
|---|---|---|
| `title_id` | `str` | IMDBx title ID, e.g. `"tt7441658"` |
| `series_name` | `str` | Series title |
| `type` | `str \| None` | Content type, e.g. `"TV Series"` |
| `years` | `str \| None` | Run years, e.g. `"2017–2021"` |
| `content_rating` | `str \| None` | Audience rating, e.g. `"TV-PG"` |
| `episode_duration` | `str \| None` | Typical episode length, e.g. `"24m"` |
| `imdb_rating` | `str \| None` | Aggregate rating, e.g. `"8.2/10"` |
| `rating_count` | `str \| None` | Number of ratings, e.g. `"47K"` |
| `popularity` | `str \| None` | IMDBx popularity rank |
| `tags` | `list[str]` | Genre and style tags |

---

## CLI

After installing, the `imdbx` command is available system-wide:

```bash
imdbx tt7441658                     # Black Clover, all seasons
imdbx tt0903747                     # Breaking Bad
imdbx tt7441658 --seasons 1 2       # specific seasons only
imdbx tt7441658 --output out.json   # save results to a JSON file
imdbx tt7441658 --download-images   # also download cover art to ./images/
imdbx tt7441658 --images-dir ~/pics # download cover art to a custom directory
imdbx tt7441658 --meta-only         # series metadata only — no browser needed
imdbx --load out.json               # display a previously saved JSON file
imdbx tt7441658 --pool-size 8       # increase concurrency for faster scraping
imdbx tt7441658 --debug             # verbose output: HTTP, browser events, timing
```

### `--test` — testing mode

```bash
# Run the full offline unit-test suite (no network required)
imdbx --test

# Live end-to-end smoke test — fetches real data and checks key fields
imdbx --test tt7441658
imdbx --test tt0903747
```

`--test` alone runs `pytest` on the bundled test suite and exits with pytest's return code (0 = all passed). Requires `pip install "IMDBx[dev]"`.

`--test <TITLE_ID>` hits the real IMDBx API, verifies that metadata and episode data are populated correctly, and prints a coloured ✓/✗ summary. Requires a network connection and Playwright/Chromium.

---

## Architecture

```
imdbx/
├── __init__.py     ← public API  (title, season, episode, metadata, load)
├── models.py       ← dataclasses (TitleInfo, SeriesMetadata, Episode)
├── cli.py          ← imdbx command — all flags with full help text
├── _scraper.py     ← orchestration: coordinates HTTP + browser + images
├── _http.py        ← niquests connection pool + async image downloader
├── _browser.py     ← Playwright pool + "Show more" expansion detection
├── _parse.py       ← BeautifulSoup parsers (zero hardcoded class names)
├── _display.py     ← terminal colour output
└── _log.py         ← shared ANSI colour helpers + debug flag
tests/
├── test_models_episode_dataclass.py   ← Episode field and repr tests
├── test_models_series_title_info.py   ← TitleInfo + save/load round-trip
├── test_parse_episode_cards.py        ← HTML → Episode parsing
├── test_parse_series_metadata.py      ← HTML → SeriesMetadata parsing
└── test_http_session_and_load.py      ← HTTP session and JSON load tests
```

Three-layer hybrid approach:

- **Layer 1** (niquests): lightweight HTTP for metadata, season counts, and image downloads
- **Layer 2** (Playwright): headless Chromium for JS-rendered episode pages with "Show more" expansion
- **Layer 3** (async): concurrent cover-image fetching via `niquests.AsyncSession`

---

## Running tests

Tests require a source checkout:

```bash
git clone https://github.com/ENC4YP7ED/IMDBx
cd IMDBx
pip install -e ".[dev]"

# Via pytest directly
pytest

# Via the CLI — same result
imdbx --test

# Live smoke test against a real title (network + Chromium required)
imdbx --test tt7441658
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-change`
3. Install dev dependencies: `pip install -e ".[dev]"`
4. Make your changes and add tests
5. Verify everything passes: `imdbx --test`
6. Open a pull request

---

## Changelog

### 1.1.4
- `imdbx.__version__` now reflects the installed package version via `importlib.metadata`

### 1.1.3
- Fixed `AttributeError: type object 'C' has no attribute 'BRED'` that crashed `imdbx --test` and smoke-test error output

### 1.1.2
- Fixed `air_date` parsing returning episode title prefix alongside the date (e.g. `S1.E1 ∙ PilotSun, Jan 20, 2008`); inline `span`/`time` elements are now searched before `div` containers

### 1.1.1
- Fixed `imdbx --test` from a PyPI install incorrectly resolving to another package's `tests/` directory
- Fixed `SyntaxError` on Python 3.10/3.11 caused by backslash inside f-string expressions

### 1.1.0
- Switched scraping target from imdbx.com to imdb.com
- Fixed genre tag deduplication and filtering of IMDb navigation links
- Initial public release

---

## License

MIT — see [LICENSE](LICENSE) for details.
