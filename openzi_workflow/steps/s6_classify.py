"""Step 6 — classify the account as test vs prod over [start, end].

Prod = a CreateAccount event is present in-window (the account was created inside
the audited window, so the whole history was observed). Test = none. The test/stub
paths force is_test=true regardless: a run that skipped the domain purchase, or the
stub workflow, can never produce a prod-grade proof. Extension point: prod will also
run a rule-based check over the window's events (deferred).

NOTE (account-type assumption): the CreateAccount discriminator assumes a standalone
account whose own event history records its creation. Org-member accounts (used for
recoverable testing) never see CreateAccount, so they always classify as test — the
intended behaviour today.
"""

from __future__ import annotations

from datetime import datetime

from .. import config, events


def classify(ct, start: datetime, end: datetime, *, forced_test: bool,
             sleep=None, now=None) -> bool:
    if forced_test:
        return True
    kwargs = {"poll_max": config.DELIVERY_POLL_MAX_SECONDS,
              "interval": config.DELIVERY_POLL_INTERVAL}
    if sleep is not None:
        kwargs["sleep"] = sleep
    if now is not None:
        kwargs["now"] = now
    return events.classify_is_test(ct, start, end, **kwargs)
