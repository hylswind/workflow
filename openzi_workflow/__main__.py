"""Sequence the eight steps. Reads config from the environment (workflow inputs +
secrets), runs steps 1-4 on the account's root key, waits, then runs steps 6-8 on the minted
event-reader key. Writes statement.json; the workflow YAML signs and uploads it.

The stub workflow sets OPENZI_STUB=1: the launched instance runs the wait+marker
stub instead of itworker, and the verdict is forced isTest=true. The skip-domain
input likewise forces isTest=true (and tells itworker to reuse an owned domain)."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from . import clients, config, userdata
from .steps import (s1_iam, s2_launch, s3_lock_signin, s4_delete_root, s5_wait,
                    s6_classify, s7_await_marker, s8_statement)


@dataclass
class RunConfig:
    root_key: str
    root_secret: str
    api_key: str
    start: int          # unix timestamp, seconds
    end: int            # unix timestamp, seconds
    domain: str
    contact: dict
    skip_domain: bool
    stub: bool
    region: str

    @classmethod
    def from_env(cls, env: dict | None = None) -> "RunConfig":
        e = os.environ if env is None else env
        req = ["OPENZI_ROOT_KEY", "OPENZI_ROOT_SECRET", "OPENZI_START", "OPENZI_END", "OPENZI_DOMAIN"]
        stub = e.get("OPENZI_STUB", "0") in ("1", "true", "True")
        if not stub:  # the stub run needs neither the API key nor contact details
            req += ["OPENZI_API_KEY"]
        missing = [k for k in req if not e.get(k)]
        if missing:
            raise ValueError(f"workflow: missing env {missing}")
        start, end = _parse_ts(e["OPENZI_START"]), _parse_ts(e["OPENZI_END"])
        if end <= start:
            raise ValueError("workflow: end must be after start")
        contact = json.loads(e.get("OPENZI_CONTACT") or "{}")
        return cls(
            root_key=e["OPENZI_ROOT_KEY"], root_secret=e["OPENZI_ROOT_SECRET"],
            api_key=e.get("OPENZI_API_KEY", ""), start=start, end=end,
            domain=e["OPENZI_DOMAIN"], contact=contact,
            skip_domain=e.get("OPENZI_SKIP_DOMAIN", "0") in ("1", "true", "True"),
            stub=stub, region=e.get("OPENZI_REGION") or config.REGION)


def _parse_ts(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"workflow: timestamp must be unix seconds, got {value!r}") from None


def _dt(ts: int) -> datetime:
    """Epoch seconds -> aware UTC datetime, for the CloudTrail LookupEvents window."""
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def run(cfg: RunConfig, log=print) -> dict:
    end_epoch = cfg.end  # already unix seconds
    root = clients.root_session(cfg.root_key, cfg.root_secret)
    iam = root.client("iam")
    account_id = root.client("sts").get_caller_identity()["Account"]

    log("step 1: create admin role + event-reader user")
    ids = s1_iam.create_identities(iam)

    if cfg.stub:
        log("step 2: launch instance (STUB user-data)")
        user_data = userdata.build_stub_userdata(
            region=cfg.region, end_epoch=end_epoch, ok_param=config.SETUP_OK_PARAM)
    else:
        log("step 2: launch itworker instance")
        user_data = userdata.build_setup_userdata(
            repo=config.ITWORKER_REPO, commit=config.ITWORKER_COMMIT, region=cfg.region,
            domain=cfg.domain, end_epoch=end_epoch, api_key=cfg.api_key,
            skip_domain=cfg.skip_domain, contact=cfg.contact)
    instance_id = s2_launch.launch(root.client("ec2"), root.client("ssm"),
                                   user_data, ids["profile_name"])
    log(f"  instance {instance_id}")

    log("step 3: lock console sign-in")
    s3_lock_signin.lock(root.client("ec2"), root.client("signin"), account_id)

    log("step 4: delete root access key")
    s4_delete_root.delete_root_key(iam, cfg.root_key)

    log(f"step 5: wait until end + {config.T_SLACK_SECONDS}s")
    s5_wait.wait_until(end_epoch + config.T_SLACK_SECONDS)

    reader = clients.reader_session(ids["reader_key"], ids["reader_secret"])
    ct = reader.client("cloudtrail")

    log("step 6: classify test vs prod")
    is_test = s6_classify.classify(ct, _dt(cfg.start), _dt(cfg.end),
                                   forced_test=cfg.stub or cfg.skip_domain)
    log(f"  isTest={is_test}")

    log("step 7: await itworker setup marker")
    s7_await_marker.await_marker(ct)

    log("step 8: write statement")
    statement = s8_statement.build_statement(cfg.start, cfg.end, cfg.domain, is_test)
    s8_statement.write_statement(config.STATEMENT_FILE, statement)
    log(f"  wrote {config.STATEMENT_FILE}: {statement}")
    return statement


def main(argv: list[str] | None = None) -> int:
    cfg = RunConfig.from_env()
    run(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
