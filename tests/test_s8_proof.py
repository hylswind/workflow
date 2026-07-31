import json

from openzi_workflow.steps import s8_proof


def test_build_proof_shape():
    p = s8_proof.build_proof("2026-07-30T00:00:00Z", "2026-07-30T01:00:00Z", "example.com", True)
    assert p == {"start": "2026-07-30T00:00:00Z", "end": "2026-07-30T01:00:00Z",
                 "domain": "example.com", "is_test": True}


def test_write_proof_roundtrips(tmp_path):
    path = tmp_path / "proof.json"
    proof = s8_proof.build_proof("s", "e", "d", False)
    s8_proof.write_proof(path, proof)
    assert json.loads(path.read_text()) == proof
