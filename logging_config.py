"""Centralized logging for Rugpull AI Hardcore."""
from __future__ import annotations
import logging
import sys
from pathlib import Path

def setup_logging(level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """Configure root logger. Call once at app start."""
    root = logging.getLogger()
    if root.handlers:
        return logging.getLogger("rugpull")

    numeric = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(numeric)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setFormatter(fmt)
        root.addHandler(fh)

    # Quiet noisy libs
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    return logging.getLogger("rugpull")

log = setup_logging()
