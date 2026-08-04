"""Step 1 against moto: the admin role+profile (AdministratorAccess, EC2 trust) and
the event-reader user (LookupEvents only) + access key."""

import json

import boto3
import pytest
from moto import mock_aws

from openzp_workflow import config
from openzp_workflow.steps import s1_iam


@pytest.fixture
def iam():
    with mock_aws():
        yield boto3.client("iam", region_name="us-east-1")


def test_creates_admin_role_profile_and_reader(iam):
    out = s1_iam.create_identities(iam)
    assert out["profile_name"] == config.ADMIN_ROLE
    assert out["reader_key"] and out["reader_secret"]

    # admin role: EC2 trust + AdministratorAccess, and an instance profile holding it
    role = iam.get_role(RoleName=config.ADMIN_ROLE)["Role"]
    assert role["AssumeRolePolicyDocument"]["Statement"][0]["Principal"]["Service"] == "ec2.amazonaws.com"
    attached = iam.list_attached_role_policies(RoleName=config.ADMIN_ROLE)["AttachedPolicies"]
    assert any(p["PolicyName"] == "AdministratorAccess" for p in attached)
    prof = iam.get_instance_profile(InstanceProfileName=config.ADMIN_ROLE)["InstanceProfile"]
    assert prof["Roles"][0]["RoleName"] == config.ADMIN_ROLE

    # event reader: scoped to cloudtrail:LookupEvents only
    pol = iam.get_user_policy(UserName=config.EVENT_READER_USER, PolicyName="read-events")
    doc = pol["PolicyDocument"]
    if isinstance(doc, str):
        doc = json.loads(doc)
    assert doc["Statement"][0]["Action"] == "cloudtrail:LookupEvents"
