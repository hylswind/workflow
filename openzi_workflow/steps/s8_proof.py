"""Step 8 — write proof.json. The workflow YAML then signs it with GitHub artifact
attestation (Sigstore) and uploads it as a run artifact. The signed envelope binds
this verdict to the repo + pinned commit + workflow file; the JSON itself is the
verdict."""

from __future__ import annotations

import json
from pathlib import Path


def build_proof(start_iso: str, end_iso: str, domain: str, is_test: bool) -> dict:
    return {"start": start_iso, "end": end_iso, "domain": domain, "is_test": is_test}


def write_proof(path: str | Path, proof: dict) -> None:
    Path(path).write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
