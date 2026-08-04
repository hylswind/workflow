"""Step 4 — root's last act: delete its own access key. After this the workflow's
root session is dead; steps 5-8 run on the event-reader key (and the itworker
instance runs on the admin role). There is no standing credential a human can use."""

from __future__ import annotations


def delete_root_key(iam, root_key_id: str) -> None:
    iam.delete_access_key(AccessKeyId=root_key_id)
