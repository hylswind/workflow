"""The stub only rehearses production if the two workflow files stay in lockstep, and
if what they sign matches what the package says it signs. Both files assert as much in
prose; these tests make the claims fail loudly instead of rotting silently.

Merging them into one reusable workflow would enforce this structurally but break the
trust model: the attestation's workflow identity would become the shared file, so a
stub statement would be signed under the same identity as a production one."""

from pathlib import Path

import yaml

from openzp_workflow import config

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
ON = True  # PyYAML reads the `on:` key as a boolean (YAML 1.1 truthiness)


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


def _job(wf: dict) -> dict:
    (job,) = wf["jobs"].values()
    return job


def _step_env(wf: dict) -> dict:
    for step in _job(wf)["steps"]:
        if "env" in step:
            return step["env"]
    raise AssertionError("no step carries an env block")


def _attest_step(wf: dict) -> dict:
    (step,) = [s for s in _job(wf)["steps"]
               if str(s.get("uses", "")).startswith("actions/attest")]
    return step


def test_stub_and_production_take_the_same_inputs():
    prod, stub = _load("openzp.yml"), _load("openzp-stub.yml")
    assert (set(stub[ON]["workflow_dispatch"]["inputs"])
            == set(prod[ON]["workflow_dispatch"]["inputs"]))


def test_stub_and_production_pass_the_same_env():
    prod, stub = _load("openzp.yml"), _load("openzp-stub.yml")
    # OPENZP_STUB is the one intended divergence: it picks the payload and the verdict.
    assert set(_step_env(stub)) - {"OPENZP_STUB"} == set(_step_env(prod))


def test_both_workflows_sign_what_the_package_writes():
    for name in ("openzp.yml", "openzp-stub.yml"):
        with_ = _attest_step(_load(name))["with"]
        assert with_["predicate-type"] == config.PREDICATE_TYPE
        assert with_["subject-path"] == config.STATEMENT_FILE
        assert with_["predicate-path"] == config.STATEMENT_FILE
