"""Step 5 — wait until end + t. t (config.T_SLACK_SECONDS) exists only to absorb
event-history delivery latency; s6 polls, so correctness doesn't depend on it."""

from __future__ import annotations

import time


def wait_until(epoch: float, *, poll: float = 15.0, sleep=time.sleep, now=time.time) -> None:
    while now() < epoch:
        sleep(min(poll, epoch - now()))
