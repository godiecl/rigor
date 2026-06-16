#  Copyright (c) 2026. Diego Urrutia-Astorga <durrutia@ucn.cl>

import datetime
import logging
import time
from contextlib import contextmanager
from datetime import timedelta
from typing import Generator

import humanize


@contextmanager
def benchmark(
        operation_name: str | None = None,
        log: logging.Logger | None = None,
) -> Generator[None, None, None]:
    """Measure elapsed time for a code block and log a human-readable duration."""

    # the log
    log = log or logging.getLogger(__name__)

    # start time
    start_ns: int = time.perf_counter_ns()

    try:
        yield
    finally:
        elapsed_ns: int = time.perf_counter_ns() - start_ns
        delta: timedelta = datetime.timedelta(seconds=elapsed_ns / 1_000_000_000)

        human_time: str = humanize.precisedelta(
            delta, minimum_unit="microseconds", format="%.2f"
        )

        if operation_name:
            log.debug(f"⏱️{operation_name} executed in {human_time}")
        else:
            log.debug(f"⏱️executed in {human_time}")
