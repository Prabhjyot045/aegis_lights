from __future__ import annotations

import logging
from typing import Literal


def configure_logging(level: int | Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = logging.INFO) -> None:
    """Configure root logging for the controller."""

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
