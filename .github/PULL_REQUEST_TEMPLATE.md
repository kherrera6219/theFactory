## Summary
<!-- One paragraph describing the purpose and approach of this PR. -->

## Type of change
- [ ] Bug fix
- [ ] New feature
- [ ] Refactor
- [ ] Documentation
- [ ] Security fix
- [ ] CI / DevOps
- [ ] Breaking change (describe below)

## Related issues
<!-- Closes #<issue-number> -->

## Changes made
<!-- Bullet list of the key changes. Focus on *why*, not just *what*. -->

-
-

## Test plan
<!-- How did you verify this works? What tests were added or modified? -->

- [ ] Unit tests added / updated
- [ ] Integration tests pass (`pytest`)
- [ ] TypeScript tests pass (`npm test` in apps/mission-control)
- [ ] Manually tested against local stack (`docker compose up`)
- [ ] Relevant edge cases covered

## Security checklist
- [ ] No secrets, credentials, or API keys committed
- [ ] No new hardcoded default values for auth/keys
- [ ] New API endpoints have auth guards and are tested
- [ ] Input validation added for any new user-facing fields
- [ ] `bandit` SAST passes (zero high/critical findings)
- [ ] `pip-audit` / `npm audit` — no new high/critical CVEs introduced

## PR checklist
- [ ] CI checks pass (lint, test, build, security scans)
- [ ] Coverage does not regress below 80% overall
- [ ] New env variables added to `.env.example` with `CHANGE_ME_` placeholders
- [ ] Breaking API contract changes documented in this description
- [ ] Relevant docs updated (`CONTRIBUTING.md`, `SECURITY.md`, `README.md`)
- [ ] Commit messages follow Conventional Commits format
