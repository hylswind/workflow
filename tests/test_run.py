"""RunConfig parsing + the run() orchestration (steps stubbed): verdict propagation,
stub vs real user-data selection, and root-key deletion."""

from datetime import datetime, timezone

import pytest

from openzi_workflow import __main__ as m


# ---------- RunConfig.from_env ----------

def _env(**over):
    base = {"OPENZI_ROOT_KEY": "AKIA", "OPENZI_ROOT_SECRET": "sec",
            "OPENZI_API_KEY": "key", "OPENZI_START": "2026-07-30T00:00:00Z",
            "OPENZI_END": "2026-07-30T01:00:00Z", "OPENZI_DOMAIN": "example.com",
            "OPENZI_CONTACT": '{"Email":"a@b.c"}'}
    base.update(over)
    return base


def test_from_env_parses():
    cfg = m.RunConfig.from_env(_env(OPENZI_SKIP_DOMAIN="true"))
    assert cfg.domain == "example.com" and cfg.skip_domain is True and cfg.stub is False
    assert cfg.start < cfg.end


def test_from_env_rejects_end_before_start():
    with pytest.raises(ValueError, match="end must be after start"):
        m.RunConfig.from_env(_env(OPENZI_END="2026-07-29T00:00:00Z"))


def test_from_env_stub_does_not_require_api_key():
    env = _env(OPENZI_STUB="1")
    del env["OPENZI_API_KEY"]
    cfg = m.RunConfig.from_env(env)
    assert cfg.stub is True


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
        start=datetime(2026, 7, 30, tzinfo=timezone.utc),
        end=datetime(2026, 7, 30, 1, tzinfo=timezone.utc),
        domain="example.com", contact={}, skip_domain=skip, stub=stub, region="us-east-1")


def _patch(monkeypatch):
    captured = {}
    monkeypatch.setattr(m.clients, "root_session",
                        lambda *a: FakeSession({"iam": object(), "sts": FakeSts(),
                                                "ec2": object(), "ssm": object(), "signin": object()}))
    monkeypatch.setattr(m.clients, "reader_session",
                        lambda *a: FakeSession({"cloudtrail": object()}))
    monkeypatch.setattr(m.s1_iam, "create_identities",
                        lambda iam: {"profile_name": "openzi-admin", "reader_key": "rk", "reader_secret": "rs"})
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
    monkeypatch.setattr(m.s8_proof, "write_proof",
                        lambda path, proof: captured.__setitem__("written", proof))
    return captured


def test_run_production_path(monkeypatch):
    captured = _patch(monkeypatch)
    proof = m.run(_cfg(), log=lambda *_: None)
    assert captured["ud"] == "SETUP_UD"
    assert captured["root_deleted"] == "AKIA"
    assert captured["awaited"] is True
    assert proof["is_test"] is False and proof["domain"] == "example.com"
    assert captured["written"] == proof


def test_run_stub_forces_test_and_stub_userdata(monkeypatch):
    captured = _patch(monkeypatch)
    proof = m.run(_cfg(stub=True), log=lambda *_: None)
    assert captured["ud"] == "STUB_UD"
    assert proof["is_test"] is True


def test_run_skip_domain_forces_test(monkeypatch):
    _patch(monkeypatch)
    proof = m.run(_cfg(skip=True), log=lambda *_: None)
    assert proof["is_test"] is True
