# openzi-workflow

The GitHub Actions side of openzi. It drives the target AWS account into a
state no human can control, then — being pinned by its own commit and run in public
— acts as the trusted verifier and emits a signed **statement** of what it saw.

## Trust model

The workflow file and this code are fixed by the commit the run checks out. The run
is public. The final `statement.json` is only a claim; the GitHub artifact
attestation (Sigstore) signed over it is the proof, letting a verifier confirm the
statement was produced by *this repo at this commit by this workflow file* —
without re-deriving anything themselves. That chain
(public run + commit-pinned code + signed verdict) is the entire trust anchor; there
is no measured AMI or hardware attestation anymore.

## What the run does (single job, in order)

1. With the account's root key: create an **admin role** (EC2 trust, AdministratorAccess) and
   an **event-reader user** (`cloudtrail:LookupEvents` only).
2. Launch one EC2 (AL2023, admin instance profile, default VPC, public IP) whose
   user-data clones the **pinned itworker** commit and runs its setup.
3. Enable the AWS Sign-In lockout (deny console sign-in unless from an empty anchor
   VPC; billing user exempt).
4. Delete the account's root access key — root's last act.
5. Wait until `end + t` (`t` = `config.T_SLACK_SECONDS`, absorbs event-history lag).
6. Classify over `[start, end]`: a `CreateAccount` event in-window ⇒ prod
   (`isTest=false`), none ⇒ test. Polls to beat delivery latency.
7. Wait for itworker's setup marker (a distinct SSM parameter **name** for
   success vs failure — so a failure fails the run instead of hanging).
8. Write `statement.json = {start, end, domain, isTest}`; the YAML signs + uploads it.

## Inputs

`start`, `end` (Unix timestamps, seconds), `domain`, `contact` (registration contact JSON), and
`skip_domain` (reuse an owned domain, forces `isTest=true`) are `workflow_dispatch`
inputs. `end` must be within ~4h of trigger (the itworker setup tail + the 6h job cap).

Secrets: `ROOT_KEY_ID`, `ROOT_SECRET`, `CONTROL_API_KEY`.

## The pin

`config.ITWORKER_REPO` / `config.ITWORKER_COMMIT` pin the itworker code the launched
instance clones — currently `hylswind/itworker` at `main`. **For a production run,
pin `ITWORKER_COMMIT` to an exact commit sha**: `main` is a moving target, so what
runs would not be fixed by this workflow's signed commit. Because the workflow's own
signed commit contains this pin, itworker is transitively pinned too.

## Testing

- `pip install -r requirements-dev.txt && pytest` — offline unit tests (moto +
  fakes), no AWS account.
- e2e (`tests/e2e/`, opt-in via env, destructive): triggers the real workflow. Two
  variants — the full `openzi.yml` (pinned itworker) and `openzi-stub.yml` (the
  wait+marker stub, to test the workflow's own logic without a platform bring-up).

## Verifying a statement

```
gh run download <run-id> -n openzi-statement
gh attestation verify statement.json \
   --repo <owner>/<repo> \
   --predicate-type https://openzi.dev/verifiable-deployment/v1
cat statement.json
```

`gh attestation verify` must report a Sigstore/Rekor attestation naming this repo,
the pinned commit, and the **production** `openzi.yml` workflow. A statement from
the stub workflow is attested under a different workflow identity and is
`isTest=true`, so it can never pass as production.
