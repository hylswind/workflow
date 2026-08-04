import json

from openzp_workflow.steps import s8_statement


def test_build_statement_shape():
    s = s8_statement.build_statement(1700000000, 1700003600, "example.com", True)
    assert s == {"start": 1700000000, "end": 1700003600,
                 "domain": "example.com", "isTest": True}


def test_write_statement_roundtrips(tmp_path):
    path = tmp_path / "statement.json"
    statement = s8_statement.build_statement(1700000000, 1700003600, "d", False)
    s8_statement.write_statement(path, statement)
    assert json.loads(path.read_text()) == statement
