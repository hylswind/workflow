"""Step 1 — create the two identities, using B's root credentials:

- an admin ROLE + instance profile (EC2 trust, AdministratorAccess) that the
  launched instance (and its ASG replacements) run under;
- an event-reader USER scoped to cloudtrail:LookupEvents only, whose access key the
  workflow keeps in runner memory to read event history after root is gone.
"""

from __future__ import annotations

import json

from .. import config

_EC2_TRUST = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"},
                   "Action": "sts:AssumeRole"}]})

_READER_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Action": "cloudtrail:LookupEvents", "Resource": "*"}]})


def create_identities(iam) -> dict:
    """Returns {profile_name, reader_key, reader_secret}. The admin role and its
    instance profile share the name (config.ADMIN_ROLE)."""
    iam.create_role(RoleName=config.ADMIN_ROLE, AssumeRolePolicyDocument=_EC2_TRUST)
    iam.attach_role_policy(RoleName=config.ADMIN_ROLE,
                           PolicyArn="arn:aws:iam::aws:policy/AdministratorAccess")
    iam.create_instance_profile(InstanceProfileName=config.ADMIN_ROLE)
    iam.add_role_to_instance_profile(InstanceProfileName=config.ADMIN_ROLE,
                                     RoleName=config.ADMIN_ROLE)

    iam.create_user(UserName=config.EVENT_READER_USER)
    iam.put_user_policy(UserName=config.EVENT_READER_USER,
                        PolicyName="read-events", PolicyDocument=_READER_POLICY)
    key = iam.create_access_key(UserName=config.EVENT_READER_USER)["AccessKey"]
    return {"profile_name": config.ADMIN_ROLE,
            "reader_key": key["AccessKeyId"], "reader_secret": key["SecretAccessKey"]}
