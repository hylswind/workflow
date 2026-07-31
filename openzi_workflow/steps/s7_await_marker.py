"""Step 7 — wait for itworker's setup result. itworker always writes a marker (a
distinct parameter NAME for success vs failure), so the workflow learns the outcome
instead of blocking until its job times out. A failure marker fails the run — no
statement is signed."""

from __future__ import annotations

from .. import config, events


class SetupFailed(Exception):
    pass


def await_marker(ct, *, sleep=None, now=None) -> None:
    kwargs = {"timeout": config.MARKER_POLL_TIMEOUT_SECONDS,
              "interval": config.MARKER_POLL_INTERVAL}
    if sleep is not None:
        kwargs["sleep"] = sleep
    if now is not None:
        kwargs["now"] = now
    result = events.await_setup_marker(ct, config.SETUP_OK_PARAM, config.SETUP_FAILED_PARAM, **kwargs)
    if result != "ok":
        raise SetupFailed("itworker setup reported failure (see /openzi/setup/failed in the target account)")
