"""The launched instance's user-data: real setup (clone pinned itworker + run setup
with the passed config) and the e2e stub (wait then write the success marker)."""

import json

from openzp_workflow import config, userdata


def test_setup_userdata_clones_pin_and_passes_config():
    ud = userdata.build_setup_userdata(
        repo="owner/openzp-itworker", commit="abcdef1", region="us-east-1",
        domain="example.com", end_epoch=1700000000, api_key="s3cr3t",
        skip_domain=True, contact={"Email": "a@b.c"})
    assert "git checkout abcdef1" in ud
    assert "github.com/owner/openzp-itworker" in ud
    assert "python3.11 -m openzp_itworker setup" in ud
    assert "OPENZP_DOMAIN=example.com" in ud
    assert "OPENZP_END=1700000000" in ud
    assert "OPENZP_SKIP_DOMAIN=1" in ud
    assert "s3cr3t" in ud
    # contact JSON survives shell-quoting
    assert json.dumps({"Email": "a@b.c"}) in ud


def test_setup_userdata_stops_tracing_before_the_secrets():
    ud = userdata.build_setup_userdata(
        repo="owner/openzp-itworker", commit="abcdef1", region="us-east-1",
        domain="example.com", end_epoch=1700000000, api_key="s3cr3t",
        skip_domain=True, contact={"Email": "a@b.c"})
    # -x echoes each command to the console log, which get-console-output serves.
    assert ud.index("set +x") < ud.index("s3cr3t")
    assert ud.index("set +x") < ud.index("OPENZP_CONTACT")


def test_stub_userdata_waits_then_writes_marker():
    ud = userdata.build_stub_userdata(region="us-east-1", end_epoch=1700000000,
                                      ok_param=config.SETUP_OK_PARAM)
    assert "1700000001" in ud                       # end + 1
    assert f"put-parameter --name {config.SETUP_OK_PARAM}" in ud
    assert "git clone" not in ud                     # no itworker
