from __future__ import annotations

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(level.upper())
    handler = logging.StreamHandler(sys.stdout)
    fmt = "%(asctime)s %(levelname)-7s %(name)s :: %(message)s"
    handler.setFormatter(logging.Formatter(fmt))
    root.addHandler(handler)

    for noisy in ("aiogram.event", "apscheduler.scheduler", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
