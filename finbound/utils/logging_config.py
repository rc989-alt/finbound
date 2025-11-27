import logging
from pathlib import Path
from typing import Optional


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Configure basic logging for FinBound.

    Parameters
    ----------
    level:
        Logging level name (e.g., "INFO", "DEBUG").
    log_file:
        Optional path to log output. When not provided, logs go to stderr.
    """

    logging_level = getattr(logging, level.upper(), logging.INFO)
    log_kwargs = {
        "level": logging_level,
        "format": "[%(levelname)s] %(name)s - %(message)s",
    }

    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        log_kwargs["filename"] = log_file

    logging.basicConfig(**log_kwargs)

