"""Step 2 — launch the itworker instance: latest AL2023, the admin instance
profile, a public IP in the default VPC, carrying the setup (or stub) user-data.

The IAM instance profile from step 1 is eventually consistent, so RunInstances can
transiently fail 'Invalid IAM Instance Profile' — retry that specific error briefly."""

from __future__ import annotations

import time

from botocore.exceptions import ClientError

from .. import config

_PROFILE_ERRORS = ("InvalidParameterValue", "InvalidIamInstanceProfile")
_PROFILE_WAIT = 90


def launch(ec2, ssm, user_data: str, profile_name: str,
           *, sleep=time.sleep, now=time.monotonic) -> str:
    ami = ssm.get_parameter(Name=config.BASE_AMI_PARAM)["Parameter"]["Value"]
    subnet = _default_public_subnet(ec2)

    deadline = now() + _PROFILE_WAIT
    while True:
        try:
            resp = ec2.run_instances(
                ImageId=ami, InstanceType="t3.small", MinCount=1, MaxCount=1,
                IamInstanceProfile={"Name": profile_name},
                NetworkInterfaces=[{"DeviceIndex": 0, "SubnetId": subnet,
                                    "AssociatePublicIpAddress": True,
                                    "DeleteOnTermination": True}],
                UserData=user_data,
                TagSpecifications=[{"ResourceType": "instance",
                                    "Tags": [{"Key": "Name", "Value": "openzp-itworker"}]}])
            return resp["Instances"][0]["InstanceId"]
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in _PROFILE_ERRORS and "Instance Profile" in str(exc) and now() < deadline:
                sleep(3)
                continue
            raise


def _default_public_subnet(ec2) -> str:
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}]).get("Vpcs", [])
    if not vpcs:
        raise RuntimeError("no default VPC in this account/region")
    vpc_id = vpcs[0]["VpcId"]
    subnets = ec2.describe_subnets(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]},
                 {"Name": "default-for-az", "Values": ["true"]}]).get("Subnets", [])
    if not subnets:
        raise RuntimeError("default VPC has no default subnet")
    return sorted(subnets, key=lambda s: s["AvailabilityZone"])[0]["SubnetId"]
