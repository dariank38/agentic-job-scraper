"""ANSI-colored console logging formatter — no extra dependencies."""

import logging

# ── ANSI escape helpers ────────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"

# Standard foreground colors
BLACK   = "\033[30m"
RED     = "\033[31m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"
CYAN    = "\033[36m"
WHITE   = "\033[37m"

# Bright foreground colors
BRIGHT_RED     = "\033[91m"
BRIGHT_GREEN   = "\033[92m"
BRIGHT_YELLOW  = "\033[93m"
BRIGHT_BLUE    = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN    = "\033[96m"
BRIGHT_WHITE   = "\033[97m"

# ── Level colors ───────────────────────────────────────────────────────────────
LEVEL_COLORS = {
    logging.DEBUG:    DIM + CYAN,
    logging.INFO:     BRIGHT_GREEN,
    logging.WARNING:  BRIGHT_YELLOW,
    logging.ERROR:    BRIGHT_RED,
    logging.CRITICAL: BOLD + RED,
}

# ── Logger-name prefix colors (matched by substring) ──────────────────────────
# Keys are substrings of logger names; first match wins.
LOGGER_COLORS: list[tuple[str, str]] = [
    ("ollama",    BRIGHT_MAGENTA),
    ("listener",  BRIGHT_CYAN),
    ("tasks",     BRIGHT_BLUE),
    ("actions",   BLUE),
    ("website",   BRIGHT_YELLOW),
    ("telegram",  CYAN),
    ("services",  MAGENTA),
    ("routes",    BLUE),
    ("app.",      BRIGHT_WHITE),
    ("uvicorn",   DIM + WHITE),
    ("sqlalchemy", DIM + CYAN),
    ("fastapi",   DIM + WHITE),
]


def _logger_color(name: str) -> str:
    lower = name.lower()
    for key, color in LOGGER_COLORS:
        if key in lower:
            return color
    return WHITE


class ColoredFormatter(logging.Formatter):
    """Formatter that adds ANSI colors to console output."""

    def __init__(self, fmt: str | None = None, datefmt: str | None = None):
        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        level_color = LEVEL_COLORS.get(record.levelno, WHITE)
        name_color  = _logger_color(record.name)

        # Shorten logger name to last 2 parts for readability
        parts = record.name.split(".")
        short_name = ".".join(parts[-2:]) if len(parts) > 2 else record.name

        # Format timestamp (dim)
        asctime = self.formatTime(record, self.datefmt)
        ts = f"{DIM}{asctime}{RESET}"

        # Logger name with its own color
        name_str = f"{name_color}{short_name:<28}{RESET}"

        # Level name with level color, fixed width
        level_str = f"{level_color}{record.levelname:<8}{RESET}"

        # Message — colorize based on level
        msg = record.getMessage()
        colored_msg = f"{level_color}{msg}{RESET}"

        # Exception info (if any) in red
        exc_text = ""
        if record.exc_info:
            exc_text = "\n" + BRIGHT_RED + self.formatException(record.exc_info) + RESET

        return f"{ts} {name_str} {level_str} {colored_msg}{exc_text}"


def setup_colored_logging(log_file_path: str, level: int = logging.INFO) -> None:
    """Configure root logger with colored console + plain file handlers."""

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any existing handlers
    root.handlers.clear()

    # ── Console handler (colored) ──────────────────────────────────────────
    import sys
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(ColoredFormatter(datefmt="%Y-%m-%d %H:%M:%S"))

    # ── File handler (plain text, no ANSI) ────────────────────────────────
    file_handler = logging.FileHandler(log_file_path, mode="a", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root.addHandler(console)
    root.addHandler(file_handler)
