"""Step 3 — seal AWS console sign-in (same mechanism as the old bootstrap p3).

Create a dedicated, empty anchor VPC and install an AWS Sign-In resource policy that
denies console sign-in unless the request originates from that VPC. The VPC has no
Console Private Access endpoints, so nothing can ever source it → every console
sign-in (root included) is sealed until recover deletes the policy. The billing user
is exempted so the operator can still pay bills. Programmatic (SigV4) access is never
gated, so the control plane can always undo this."""

from __future__ import annotations

from .. import config


def lock(ec2, signin, account_id: str) -> str:
    vpc_id = _ensure_anchor_vpc(ec2)
    billing_arn = f"arn:aws:iam::{account_id}:user/{config.BILLING_CONSOLE_USER}"
    stmt = signin.put_resource_permission_statement(
        sourceVpc=vpc_id, requestedRegion=config.REGION,
        excludedPrincipal=billing_arn,
        clientToken=f"openzi-signin-lock-{account_id}")["statementId"]
    signin.put_console_authorization_configuration(targetId=account_id)
    return stmt


def _ensure_anchor_vpc(ec2) -> str:
    """Find-or-create the tagged empty anchor VPC; return its id (re-runnable)."""
    existing = ec2.describe_vpcs(
        Filters=[{"Name": "tag:Name", "Values": [config.SIGNIN_LOCK_VPC_TAG]}]).get("Vpcs", [])
    if existing:
        return existing[0]["VpcId"]
    resp = ec2.create_vpc(
        CidrBlock=config.SIGNIN_LOCK_VPC_CIDR,
        TagSpecifications=[{"ResourceType": "vpc",
                            "Tags": [{"Key": "Name", "Value": config.SIGNIN_LOCK_VPC_TAG}]}])
    return resp["Vpc"]["VpcId"]
