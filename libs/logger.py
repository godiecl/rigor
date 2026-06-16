#  Copyright (c) 2026. Diego Urrutia-Astorga <durrutia@ucn.cl>

import logging

import coloredlogs


def configure_logging(level: int = logging.DEBUG) -> None:
    """Configure the logging module."""
    coloredlogs.install(
        level=level,
        fmt="%(asctime)s [%(levelname)8s] %(name)s:%(lineno)d (%(process)d/%(threadName)s) - %(message)s",
        level_styles={
            "DEBUG": {"color": "black", "bright": True},
            "INFO": {"color": "green"},
            "WARNING": {"color": "magenta"},
            "ERROR": {"color": "red"},
            "CRITICAL": {"color": "red", "bold": True},
        },
        field_styles={
            "asctime": {"color": "yellow"},
            "levelname": {"bold": True},
            "name": {"color": "blue", "bold": True},
            "lineno": {"color": "magenta"},
            "process": {"color": "blue", "bold": True},
            "threadName": {"color": "cyan"},
            "message": {"color": "white"},

        },
        milliseconds=True,
    )

    # decrease the level of logger in external libraries
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("httpcore.connection").setLevel(logging.WARNING)
    logging.getLogger("httpcore.http11").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("numba.core").setLevel(logging.WARNING)
    logging.getLogger("openai._base_client").setLevel(logging.WARNING)
    logging.getLogger("pygeohash.pygeohash.geohash").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
