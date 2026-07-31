"""End-to-end: trigger the REAL workflow and verify the signed proof + platform.

Opt-in and destructive (it locks the account's console). Skipped unless OPENZI_E2E=1.
Requires the `gh` CLI authenticated for the repo, and a management-account credential
(OPENZI_MGMT_PROFILE) able to assume into the test account for verification/cleanup.

Env:
  OPENZI_E2E=1                 enable
  OPENZI_GH_REPO=owner/name    the workflow repo (gh -R)
  OPENZI_WORKFLOW=openzi.yml   workflow file (or openzi-stub.yml)
  OPENZI_DOMAIN                domain input
  OPENZI_CONTACT               contact JSON input (production workflow only)
  OPENZI_SKIP_DOMAIN=true      reuse an owned domain (no purchase)
"""

import json
import os
import subprocess
import time
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.e2e

if os.environ.get("OPENZI_E2E") != "1":
    pytest.skip("set OPENZI_E2E=1 to run the destructive workflow e2e", allow_module_level=True)

REPO = os.environ["OPENZI_GH_REPO"]
WORKFLOW = os.environ.get("OPENZI_WORKFLOW", "openzi.yml")
DOMAIN = os.environ["OPENZI_DOMAIN"]


def _gh(*args, **kw):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True, **kw).stdout


def test_workflow_produces_verifiable_test_proof():
    now = int(datetime.now(timezone.utc).timestamp())
    fields = {"start": str(now - 60),
              "end": str(now + 600),
              "domain": DOMAIN}
    if WORKFLOW == "openzi.yml":
        fields["contact"] = os.environ["OPENZI_CONTACT"]
        fields["skip_domain"] = os.environ.get("OPENZI_SKIP_DOMAIN", "true")
    args = ["workflow", "run", WORKFLOW, "-R", REPO]
    for k, v in fields.items():
        args += ["-f", f"{k}={v}"]
    _gh(*args)

    run_id = _wait_for_run(timeout=7200)
    conclusion = _run_field(run_id, "conclusion")
    assert conclusion == "success", f"run {run_id} concluded {conclusion}"

    # download + verify the signed proof
    workdir = f"/tmp/openzi-e2e-{run_id}"
    _gh("run", "download", str(run_id), "-R", REPO, "-D", workdir)
    proof = json.loads(open(f"{workdir}/openzi-proof/proof.json").read()
                       if os.path.exists(f"{workdir}/openzi-proof/proof.json")
                       else open(_find(workdir, "proof.json")).read())
    assert proof["domain"] == DOMAIN
    assert proof["is_test"] is True   # test window / stub / skip path
    _gh("attestation", "verify", _find(workdir, "proof.json"), "-R", REPO,
        "--predicate-type", "https://openzi.dev/account-verification/v1")


def _wait_for_run(timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        out = _gh("run", "list", "-R", REPO, "-w", WORKFLOW, "-L", "1",
                  "--json", "databaseId,status")
        rows = json.loads(out)
        if rows and rows[0]["status"] == "completed":
            return rows[0]["databaseId"]
        time.sleep(30)
    raise TimeoutError("workflow run did not complete")


def _run_field(run_id, field):
    return json.loads(_gh("run", "view", str(run_id), "-R", REPO, "--json", field))[field]


def _find(root, name):
    for dirpath, _dirs, files in os.walk(root):
        if name in files:
            return os.path.join(dirpath, name)
    raise FileNotFoundError(name)
