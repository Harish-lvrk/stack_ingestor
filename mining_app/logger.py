"""
logger.py — Structured logging for STAC Manager.

Outputs to:
  • Console  (coloured, human-readable)
  • logs/stac_manager.log  (rotating, 5 MB × 3 backups)
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from config import LOG_DIR, LOG_FILE

# ── Colour codes for terminal output ─────────────────────────────────────────
_GREY    = "\x1b[38;5;240m"
_CYAN    = "\x1b[36m"
_GREEN   = "\x1b[32m"
_YELLOW  = "\x1b[33m"
_RED     = "\x1b[31m"
_BOLD_R  = "\x1b[1;31m"
_RESET   = "\x1b[0m"

_LEVEL_COLOURS = {
    logging.DEBUG:    _GREY,
    logging.INFO:     _GREEN,
    logging.WARNING:  _YELLOW,
    logging.ERROR:    _RED,
    logging.CRITICAL: _BOLD_R,
}


class _ColourFormatter(logging.Formatter):
    FMT = "{asctime}  {colour}{levelname:<8}{reset}  [{name}]  {message}"

    def format(self, record: logging.LogRecord) -> str:
        colour = _LEVEL_COLOURS.get(record.levelno, _RESET)
        msg = logging.Formatter(
            self.FMT.format(
                asctime="%(asctime)s",
                colour=colour,
                levelname="%(levelname)s",
                reset=_RESET,
                name="%(name)s",
                message="%(message)s",
            ),
            datefmt="%Y-%m-%d %H:%M:%S",
            style="%",
        ).format(record)
        return msg


def get_logger(name: str) -> logging.Logger:
    """Return a named logger configured with console + file handlers."""
    logger = logging.getLogger(name)

    if logger.handlers:          # already configured (e.g. Streamlit hot-reload)
        return logger

    logger.setLevel(logging.DEBUG)

    # ── Console handler ───────────────────────────────────────────────────────
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(_ColourFormatter())
    logger.addHandler(ch)

    # ── File handler (rotating) ───────────────────────────────────────────────
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)

    logger.propagate = False
    return logger
