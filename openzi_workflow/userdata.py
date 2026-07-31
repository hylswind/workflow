"""Build the launched instance's user-data.

- setup: clone the pinned itworker code and run its setup mode with the config the
  workflow passes down (domain, end epoch, api key, contact, skip flag, repo/commit
  so replacement instances re-clone the same code).
- stub: the e2e-only mini script — wait until end+1s, then write the success marker.
  No itworker clone; used by the stub workflow to exercise the workflow end-to-end
  without a real platform bring-up.
"""

from __future__ import annotations

import json

_SETUP_TEMPLATE = r"""#!/bin/bash
set -euxo pipefail
dnf install -y git python3.11 python3.11-pip
python3.11 -m pip install boto3
rm -rf /opt/openzi-itworker
git clone https://github.com/{repo}.git /opt/openzi-itworker
cd /opt/openzi-itworker
git checkout {commit}
export AWS_DEFAULT_REGION={region}
export OPENZI_DOMAIN={domain}
export OPENZI_END={end_epoch}
export OPENZI_API_KEY={api_key}
export OPENZI_REPO={repo}
export OPENZI_COMMIT={commit}
export OPENZI_REGION={region}
export OPENZI_SKIP_DOMAIN={skip_domain}
export OPENZI_CONTACT={contact_shell}
exec python3.11 -m openzi_itworker setup
"""

# The stub writes the SAME success-marker parameter the real itworker would, so the
# workflow's step-7 poll behaves identically. It needs no itworker code.
_STUB_TEMPLATE = r"""#!/bin/bash
set -euxo pipefail
export AWS_DEFAULT_REGION={region}
while [ "$(date +%s)" -lt {end_plus_one} ]; do sleep 5; done
aws ssm put-parameter --name {ok_param} --type String --overwrite --value stub
"""


def _shquote(value: str) -> str:
    """Single-quote a value for safe use in the exported shell assignment."""
    return "'" + value.replace("'", "'\"'\"'") + "'"


def build_setup_userdata(*, repo: str, commit: str, region: str, domain: str,
                         end_epoch: int, api_key: str, skip_domain: bool,
                         contact: dict) -> str:
    return _SETUP_TEMPLATE.format(
        repo=repo, commit=commit, region=region, domain=domain, end_epoch=end_epoch,
        api_key=_shquote(api_key), skip_domain="1" if skip_domain else "0",
        contact_shell=_shquote(json.dumps(contact)))


def build_stub_userdata(*, region: str, end_epoch: int, ok_param: str) -> str:
    return _STUB_TEMPLATE.format(region=region, end_plus_one=end_epoch + 1, ok_param=ok_param)
