"""openzi-workflow — the code the GitHub Actions workflow runs on the hosted
runner. It drives the target account into an operator-inaccessible state and, being pinned
by the workflow's own commit and run publicly, is itself the trusted verifier: it
inspects account state over the audit window and emits a verdict statement that
the workflow YAML signs (the attestation is the proof).

The eight steps live in ``steps/`` (one file each) and are sequenced by
``__main__``.
"""
