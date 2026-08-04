"""RunConfig parsing + the run() orchestration (steps stubbed): verdict propagation,
stub vs real user-data selection, and root-key deletion."""

import json

import pytest

from openzp_workflow import __main__ as m


# ---------- RunConfig.from_env ----------

_CONTACT = json.dumps({"FirstName": "A", "LastName": "B", "AddressLine1": "1 Main St",
                       "City": "Taipei", "State": "TPE", "CountryCode": "TW",
                       "ZipCode": "100", "PhoneNumber": "+886.212345678",
                       "Email": "a@b.c"})


def _env(**over):
    base = {"OPENZP_ROOT_KEY": "AKIA", "OPENZP_ROOT_SECRET": "sec",
            "OPENZP_API_KEY": "key", "OPENZP_START": "1700000000",
            "OPENZP_END": "1700003600", "OPENZP_DOMAIN": "example.com",
            "OPENZP_CONTACT": _CONTACT}
    base.update(over)
    return base


def test_from_env_parses_unix_seconds():
    cfg = m.RunConfig.from_env(_env(OPENZP_SKIP_DOMAIN="true"))
    assert cfg.domain == "example.com" and cfg.skip_domain is True and cfg.stub is False
    assert (cfg.start, cfg.end) == (1700000000, 1700003600)


def test_from_env_rejects_end_before_start():
    with pytest.raises(ValueError, match="end must be after start"):
        m.RunConfig.from_env(_env(OPENZP_END="1699999999"))


def test_from_env_rejects_non_numeric_timestamp():
    with pytest.raises(ValueError, match="unix seconds"):
        m.RunConfig.from_env(_env(OPENZP_START="2026-07-30T00:00:00Z"))


def test_from_env_registering_requires_a_full_contact():
    with pytest.raises(ValueError, match="contact missing"):
        m.RunConfig.from_env(_env(OPENZP_CONTACT='{"Email":"a@b.c"}'))


def test_from_env_skip_domain_needs_no_contact():
    cfg = m.RunConfig.from_env(_env(OPENZP_CONTACT="{}", OPENZP_SKIP_DOMAIN="true"))
    assert cfg.skip_domain is True and cfg.contact == {}


def test_from_env_rejects_non_object_contact():
    with pytest.raises(ValueError, match="contact must be a JSON object"):
        m.RunConfig.from_env(_env(OPENZP_CONTACT="[]"))


# The stub changes the payload and the verdict, never the config contract: whatever a
# production run demands, a stub run demands too, so a green stub rehearses the real one.

def test_from_env_stub_still_requires_api_key():
    env = _env(OPENZP_STUB="1", OPENZP_SKIP_DOMAIN="true")
    del env["OPENZP_API_KEY"]
    with pytest.raises(ValueError, match="OPENZP_API_KEY"):
        m.RunConfig.from_env(env)


def test_from_env_stub_still_requires_a_full_contact():
    with pytest.raises(ValueError, match="contact missing"):
        m.RunConfig.from_env(_env(OPENZP_STUB="1", OPENZP_CONTACT="{}"))


# ---------- run() orchestration ----------

class FakeSts:
    def get_caller_identity(self):
        return {"Account": "123456789012"}


class FakeSession:
    def __init__(self, clients):
        self._c = clients

    def client(self, name):
        return self._c.get(name, object())


def _cfg(stub=False, skip=False):
    return m.RunConfig(
        root_key="AKIA", root_secret="sec", api_key="key",
        start=1700000000, end=1700003600,
        domain="example.com", contact={}, skip_domain=skip, stub=stub, region="us-east-1")


def _patch(monkeypatch):
    captured = {}
    monkeypatch.setattr(m.clients, "root_session",
                        lambda *a: FakeSession({"iam": object(), "sts": FakeSts(),
                                                "ec2": object(), "ssm": object(), "signin": object()}))
    monkeypatch.setattr(m.clients, "reader_session",
                        lambda *a: FakeSession({"cloudtrail": object()}))
    monkeypatch.setattr(m.s1_iam, "create_identities",
                        lambda iam: {"profile_name": "openzp-admin", "reader_key": "rk", "reader_secret": "rs"})
    monkeypatch.setattr(m.userdata, "build_setup_userdata", lambda **kw: "SETUP_UD")
    monkeypatch.setattr(m.userdata, "build_stub_userdata", lambda **kw: "STUB_UD")
    monkeypatch.setattr(m.s2_launch, "launch",
                        lambda ec2, ssm, ud, prof: captured.setdefault("ud", ud) or "i-1")
    monkeypatch.setattr(m.s3_lock_signin, "lock", lambda *a: "stmt")
    monkeypatch.setattr(m.s4_delete_root, "delete_root_key",
                        lambda iam, key: captured.__setitem__("root_deleted", key))
    monkeypatch.setattr(m.s5_wait, "wait_until", lambda *a, **k: None)
    monkeypatch.setattr(m.s6_classify, "classify",
                        lambda ct, s, e, forced_test: bool(forced_test))
    monkeypatch.setattr(m.s7_await_marker, "await_marker",
                        lambda ct: captured.__setitem__("awaited", True))
    monkeypatch.setattr(m.s8_statement, "write_statement",
                        lambda path, statement: captured.__setitem__("written", statement))
    return captured


def test_run_production_path(monkeypatch):
    captured = _patch(monkeypatch)
    statement = m.run(_cfg(), log=lambda *_: None)
    assert captured["ud"] == "SETUP_UD"
    assert captured["root_deleted"] == "AKIA"
    assert captured["awaited"] is True
    assert statement["isTest"] is False and statement["domain"] == "example.com"
    assert (statement["start"], statement["end"]) == (1700000000, 1700003600)  # unix seconds
    assert captured["written"] == statement


def test_run_stub_forces_test_and_stub_userdata(monkeypatch):
    captured = _patch(monkeypatch)
    statement = m.run(_cfg(stub=True), log=lambda *_: None)
    assert captured["ud"] == "STUB_UD"
    assert statement["isTest"] is True


def test_run_skip_domain_forces_test(monkeypatch):
    _patch(monkeypatch)
    statement = m.run(_cfg(skip=True), log=lambda *_: None)
    assert statement["isTest"] is True
