# Security policy

## Supported versions

Only the latest minor release receives security fixes. A version stops being supported when the next minor version is released.

| Version | Supported |
|---|---|
| 1.1.x | Yes |
| 1.0.x | No |

Docker images follow the same rule: use the latest `X.Y.Z` tag published on `ghcr.io`.

## Report a vulnerability

**Do not open a public issue.** Report it privately with GitHub's private vulnerability reporting: on the repository page, open the **Security** tab and click **Report a vulnerability**.

Please include:

- the affected version (git tag or image tag);
- what an attacker can do, and how to reproduce it (request, input file or commands);
- any idea of a fix, if you have one.

## What happens next

This is a course project maintained on a best-effort basis. The target times are:

| Step | Target |
|---|---|
| Acknowledge the report | 7 days |
| First assessment (confirmed or not, severity) | 14 days |
| Fix released for a confirmed high or critical vulnerability | 30 days |

A confirmed vulnerability is fixed in a `hotfix/X.Y.Z` branch and released as a patch version ([ADR-0006](docs/adr/0006-branching-model.md)). It is then disclosed in a GitHub security advisory, which can request a CVE identifier (Common Vulnerabilities and Exposures), and listed under "Security" in [CHANGELOG.md](CHANGELOG.md). Reporters are credited unless they prefer otherwise.

## Security notes for people deploying the service

- **Only load models you trust.** Model files are read with joblib, which uses Python pickle: loading a file runs code. `ARTIFACTS_DIR` must only contain models produced by your own training job, and the serving container should mount it read-only.
- **Secrets stay out of the code and the images.** Settings come from environment variables (`.env` is git-ignored and never copied into an image); pass them at run time.
- **Dependencies are pinned with hashes** in the `requirements*.lock` files ([ADR-0007](docs/adr/0007-dependency-management.md)): pip refuses a package that differs from the locked one.
