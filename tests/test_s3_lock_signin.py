"""Step 3: anchor VPC (moto EC2) + the AWS Sign-In deny-unless-VPC policy (a fake,
since moto has no signin service)."""

import boto3
import pytest
from moto import mock_aws

from openzp_workflow import config
from openzp_workflow.steps import s3_lock_signin


class FakeSignin:
    def __init__(self):
        self.stmt_kwargs = None
        self.console_target = None

    def put_resource_permission_statement(self, **kwargs):
        self.stmt_kwargs = kwargs
        return {"statementId": "stmt-1"}

    def put_console_authorization_configuration(self, targetId):
        self.console_target = targetId


@pytest.fixture
def ec2():
    with mock_aws():
        yield boto3.client("ec2", region_name="us-east-1")


def test_lock_creates_anchor_vpc_and_installs_policy(ec2):
    signin = FakeSignin()
    stmt = s3_lock_signin.lock(ec2, signin, "123456789012")
    assert stmt == "stmt-1"

    vpcs = ec2.describe_vpcs(Filters=[{"Name": "tag:Name",
                                       "Values": [config.SIGNIN_LOCK_VPC_TAG]}])["Vpcs"]
    assert len(vpcs) == 1
    assert signin.stmt_kwargs["sourceVpc"] == vpcs[0]["VpcId"]
    assert signin.stmt_kwargs["requestedRegion"] == "us-east-1"
    assert signin.stmt_kwargs["excludedPrincipal"].endswith(":user/console")
    assert signin.console_target == "123456789012"


def test_lock_is_idempotent_on_anchor_vpc(ec2):
    s3_lock_signin.lock(ec2, FakeSignin(), "123456789012")
    s3_lock_signin.lock(ec2, FakeSignin(), "123456789012")
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "tag:Name",
                                       "Values": [config.SIGNIN_LOCK_VPC_TAG]}])["Vpcs"]
    assert len(vpcs) == 1  # reused, not duplicated
