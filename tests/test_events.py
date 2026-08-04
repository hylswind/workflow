"""Event classification (test vs prod) and setup-marker detection, with a fake
CloudTrail returning canned lookup_events pages."""

import json
from datetime import datetime, timezone

import pytest

from openzp_workflow import config, events
from openzp_workflow.steps import s6_classify, s7_await_marker


def _ev(name, param_name=None, when=None):
    rec = {"eventName": name}
    if param_name is not None:
        rec["requestParameters"] = {"name": param_name}
    ev = {"EventName": name, "CloudTrailEvent": json.dumps(rec)}
    if when is not None:
        ev["EventTime"] = when
    return ev


class FakeCT:
    def __init__(self, evs):
        self._evs = evs

    def get_paginator(self, op):
        evs = self._evs

        class _P:
            def paginate(self, **kw):
                attrs = kw.get("LookupAttributes")
                sel = evs
                if attrs:
                    want = attrs[0]["AttributeValue"]
                    sel = [e for e in evs if e["EventName"] == want]
                start = kw.get("StartTime")
                if start is not None:  # undated events are treated as in-range
                    sel = [e for e in sel if e.get("EventTime", start) >= start]
                return [{"Events": sel}]

        return _P()


def _clock(values):
    seq = list(values)
    return lambda: seq.pop(0) if len(seq) > 1 else seq[0]


_START = datetime(2026, 7, 30, tzinfo=timezone.utc)
_END = datetime(2026, 7, 30, 1, tzinfo=timezone.utc)


# ---------- classify ----------

def test_createaccount_present_means_prod():
    ct = FakeCT([_ev("CreateAccount"), _ev("RunInstances")])
    assert events.classify_is_test(ct, _START, _END, now=_clock([0, 0])) is False


def test_no_createaccount_means_test_after_poll_drains():
    ct = FakeCT([_ev("RunInstances"), _ev("DeleteAccessKey")])
    is_test = events.classify_is_test(ct, _START, _END, poll_max=5, interval=1,
                                      sleep=lambda *_: None, now=_clock([0, 100]))
    assert is_test is True


def test_s6_forced_test_short_circuits():
    # forced_test must not even look at events
    assert s6_classify.classify(FakeCT([_ev("CreateAccount")]), _START, _END,
                                forced_test=True) is True


# ---------- await marker ----------

def test_await_marker_returns_ok():
    ct = FakeCT([_ev("PutParameter", config.SETUP_OK_PARAM)])
    assert events.await_setup_marker(ct, config.SETUP_OK_PARAM, config.SETUP_FAILED_PARAM,
                                     since=_START, now=_clock([0, 0])) == "ok"


def test_await_marker_ok_wins_over_failed():
    ct = FakeCT([_ev("PutParameter", config.SETUP_FAILED_PARAM),
                 _ev("PutParameter", config.SETUP_OK_PARAM)])
    assert events.await_setup_marker(ct, config.SETUP_OK_PARAM, config.SETUP_FAILED_PARAM,
                                     since=_START, now=_clock([0, 0])) == "ok"


def test_await_marker_ignores_a_marker_from_an_earlier_run():
    # Event history keeps 90 days and cannot be pruned, so a reused account still
    # carries the previous run's marker. Only the launch bound rules it out.
    ct = FakeCT([_ev("PutParameter", config.SETUP_OK_PARAM, when=_START)])
    with pytest.raises(TimeoutError):
        events.await_setup_marker(ct, config.SETUP_OK_PARAM, config.SETUP_FAILED_PARAM,
                                  since=_END, timeout=5, interval=1,
                                  sleep=lambda *_: None, now=_clock([0, 100]))


def test_s7_raises_on_failure_marker():
    ct = FakeCT([_ev("PutParameter", config.SETUP_FAILED_PARAM)])
    with pytest.raises(s7_await_marker.SetupFailed):
        s7_await_marker.await_marker(ct, _START, now=_clock([0, 0]))


def test_await_marker_times_out_when_silent():
    ct = FakeCT([_ev("PutParameter", "/openzp/unrelated")])
    with pytest.raises(TimeoutError):
        events.await_setup_marker(ct, config.SETUP_OK_PARAM, config.SETUP_FAILED_PARAM,
                                  since=_START, timeout=5, interval=1,
                                  sleep=lambda *_: None, now=_clock([0, 100]))
