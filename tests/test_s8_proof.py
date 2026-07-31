import json

from openzi_workflow.steps import s8_proof


def test_build_proof_shape():
    p = s8_proof.build_proof(1700000000, 1700003600, "example.com", True)
    assert p == {"start": 1700000000, "end": 1700003600,
                 "domain": "example.com", "is_test": True}


def test_write_proof_roundtrips(tmp_path):
    path = tmp_path / "proof.json"
    proof = s8_proof.build_proof(1700000000, 1700003600, "d", False)
    s8_proof.write_proof(path, proof)
    assert json.loads(path.read_text()) == proof
