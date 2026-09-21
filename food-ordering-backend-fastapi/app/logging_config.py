"""
Baseline logging setup.

Standard-library logging only — no external observability dependency is
added here. Structured logging / metrics / tracing tooling remains an open
question (ARCHITECTURE_REQUIREMENTS.md §7.6, Open Question #14) and is not
decided by this skeleton.
"""

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())

    if root.handlers:
        # Avoid duplicate handlers on reload (uvicorn --reload re-imports).
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s :: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root.addHandler(handler)
