import logging

from livraison_express.config import LogLevel

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging(level: LogLevel) -> None:
    """Called once by each entry point (CLI, API), never by library code."""
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
