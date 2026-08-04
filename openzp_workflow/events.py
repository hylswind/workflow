"""CloudTrail Event history helpers (management events via lookup_events — no trail
required). Two jobs:

- classify the account over [start, end]: a CreateAccount event in-window means the
  account was born inside the audited window, so its ENTIRE history was observed →
  prod (is_test=false); its absence → test. CloudTrail delivery lags (~15 min worst
  case), so we poll before concluding "absent".
- await the itworker setup marker: an SSM PutParameter whose parameter name is the
  success or failure marker.
"""

from __future__ import annotations

import json
import time
from datetime import datetime


def _parse(event: dict) -> dict:
    """Return the decoded CloudTrail event record (the CloudTrailEvent JSON string),
    falling back to the lookup_events envelope fields."""
    raw = event.get("CloudTrailEvent")
    if raw:
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            pass
    return {"eventName": event.get("EventName")}


def _iter_events(ct, *, start: datetime | None = None, end: datetime | None = None,
                 attributes: list[dict] | None = None):
    kwargs: dict = {}
    if start is not None:
        kwargs["StartTime"] = start
    if end is not None:
        kwargs["EndTime"] = end
    if attributes:
        kwargs["LookupAttributes"] = attributes
    for page in ct.get_paginator("lookup_events").paginate(**kwargs):
        for e in page.get("Events", []):
            yield e


def window_has_event(ct, start: datetime, end: datetime, event_name: str) -> bool:
    attrs = [{"AttributeKey": "EventName", "AttributeValue": event_name}]
    for e in _iter_events(ct, start=start, end=end, attributes=attrs):
        if _parse(e).get("eventName") == event_name:
            return True
    return False


def classify_is_test(ct, start: datetime, end: datetime, *,
                     poll_max: float = 1200, interval: float = 30,
                     sleep=time.sleep, now=time.monotonic) -> bool:
    """Poll the [start,end] window until CreateAccount appears (→ prod, False) or the
    delivery-slack deadline passes with none seen (→ test, True). Correctness does
    not depend on the wait constant t — only on this poll draining."""
    deadline = now() + poll_max
    while True:
        if window_has_event(ct, start, end, "CreateAccount"):
            return False
        if now() >= deadline:
            return True
        sleep(interval)


def await_setup_marker(ct, ok_name: str, failed_name: str, *, since: datetime,
                       timeout: float = 7200, interval: float = 30,
                       sleep=time.sleep, now=time.monotonic) -> str:
    """Poll PutParameter events until the setup success or failure marker appears.
    Returns 'ok' or 'failed'. Raises TimeoutError if neither shows up in time (the
    itworker instance died before it could write even a failure marker).

    `since` bounds the lookup at the instance launch, and is required: event history
    retains 90 days and cannot be pruned, so unbounded this would accept a marker from
    an earlier run in a reused account — and rescan that history on every poll."""
    wanted = {ok_name: "ok", failed_name: "failed"}
    deadline = now() + timeout
    attrs = [{"AttributeKey": "EventName", "AttributeValue": "PutParameter"}]
    while True:
        found: set[str] = set()
        for e in _iter_events(ct, start=since, attributes=attrs):
            rec = _parse(e)
            name = (rec.get("requestParameters") or {}).get("name")
            if name in wanted:
                found.add(name)
                if name == ok_name:
                    break         # ok wins, so no later page can change the answer
        if ok_name in found:      # success is terminal-good; it wins if both seen
            return "ok"
        if failed_name in found:
            return "failed"
        if now() >= deadline:
            raise TimeoutError("itworker setup marker never appeared")
        sleep(interval)
