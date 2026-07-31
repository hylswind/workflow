"""Step 8 — write statement.json, the verdict this run asserts. The workflow YAML
then signs it with GitHub artifact attestation (Sigstore) and uploads it as a run
artifact. The JSON itself is only a claim; the attestation — binding it to the
repo + pinned commit + workflow file — is what proves it."""

from __future__ import annotations

import json
from pathlib import Path


def build_statement(start: int, end: int, domain: str, is_test: bool) -> dict:
    """start/end are unix timestamps (seconds)."""
    return {"start": start, "end": end, "domain": domain, "isTest": is_test}


def write_statement(path: str | Path, statement: dict) -> None:
    Path(path).write_text(json.dumps(statement, indent=2) + "\n")
