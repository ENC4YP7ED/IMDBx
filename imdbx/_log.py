"""
imdbx._log
=========
Shared terminal colouring and debug-print helpers.

A single module-level flag `_DEBUG` controls whether `dbg()` prints.
Call `set_debug(True)` to enable verbose output from any entry point.
"""

from __future__ import annotations

_DEBUG: bool = False


def set_debug(enabled: bool) -> None:
    """Enable or disable verbose debug output package-wide."""
    global _DEBUG
    _DEBUG = enabled


def is_debug() -> bool:
    return _DEBUG


def dbg(*args, **kwargs) -> None:
    """Print only when debug mode is active."""
    if _DEBUG:
        print(*args, **kwargs)


# ─── ANSI colour helpers ──────────────────────────────────────────────────────

class C:
    """ANSI escape code constants."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    BGREEN  = "\033[92m"
    BYELLOW = "\033[93m"
    BBLUE   = "\033[94m"
    BCYAN   = "\033[96m"
    BWHITE  = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_BLACK= "\033[40m"


def c(text, *codes: str) -> str:
    """Wrap *text* in ANSI colour codes."""
    return "".join(codes) + str(text) + C.RESET
