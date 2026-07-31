"""Constants for the workflow steps. Single region us-east-1 (the sign-in policy,
route53domains, IAM, and the CreateAccount / marker events all live there, and
LookupEvents is region-scoped)."""

from __future__ import annotations

REGION = "us-east-1"

# --- the itworker code this workflow launches (the cross-repo pin). The launched
# instance clones exactly this; the workflow's own signed commit therefore also
# pins itworker. FILL THESE IN at repo split (owner/name + an exact 40-char sha). ---
ITWORKER_REPO = "hylswind/openzi-itworker"
ITWORKER_COMMIT = "main"  # TODO(repo-split): pin to an exact commit sha

# --- identities the workflow creates in B ---
# Must match openzi_itworker.config.ADMIN_PROFILE_NAME (the control LT runs under it).
ADMIN_ROLE = "openzi-admin"
EVENT_READER_USER = "openzi-event-reader"

BASE_AMI_PARAM = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"

# --- sign-in lockout (same mechanism as the old bootstrap p3) ---
SIGNIN_LOCK_VPC_TAG = "openzi-signin-lock-vpc"
SIGNIN_LOCK_VPC_CIDR = "10.255.0.0/28"
# The billing user the platform stack creates, exempted from the lockout. MUST match
# ConsoleUser.UserName in openzi-itworker's platform_stack.yaml.
BILLING_CONSOLE_USER = "console"

# --- timing ---
# t: absorbs CloudTrail event-history delivery latency. A floor only — s6 polls, so
# correctness does not depend on this value. 5 min for now; revisit after testing.
T_SLACK_SECONDS = 300
# s6 keeps polling the [start,end] window this long past end before concluding
# is_test (delivery can lag ~15 min); returns is_test=false the instant CreateAccount
# appears.
DELIVERY_POLL_MAX_SECONDS = 1200
DELIVERY_POLL_INTERVAL = 30
# s7 waits for the itworker marker this long (register + CFN + cert issuance tail).
MARKER_POLL_TIMEOUT_SECONDS = 7200
MARKER_POLL_INTERVAL = 30

# --- setup result markers itworker writes (the NAME encodes the outcome). MUST
# match openzi_itworker.config.SETUP_OK_PARAM / SETUP_FAILED_PARAM. ---
SETUP_OK_PARAM = "/openzi/setup/ok"
SETUP_FAILED_PARAM = "/openzi/setup/failed"

# --- proof ---
PROOF_FILE = "proof.json"
PREDICATE_TYPE = "https://openzi.dev/account-verification/v1"
