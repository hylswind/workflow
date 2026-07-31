"""Load AWS-managed policies (AdministratorAccess) in moto's IAM backend. Must be
set before moto initializes, so it lives here at collection time."""

import os

os.environ.setdefault("MOTO_IAM_LOAD_MANAGED_POLICIES", "true")
