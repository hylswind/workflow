"""boto3 sessions for the workflow's two credential identities:

- root: the account's root access key (from repo secrets). Used for steps 1-4 (create the
  admin role + event-reader user, launch the instance, lock console sign-in, then
  delete its own key as its last act).
- event_reader: the minted user's key (cloudtrail:LookupEvents only). Used for
  steps 6-7 to read event history after root is gone.
"""

from __future__ import annotations

import boto3

from . import config


def root_session(access_key: str, secret_key: str) -> boto3.Session:
    return boto3.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key,
                         region_name=config.REGION)


def reader_session(access_key: str, secret_key: str) -> boto3.Session:
    return boto3.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key,
                         region_name=config.REGION)
