# Mission Control Operator Guide

Document version: 2026.03.29  
Last updated: 2026-03-29  
Status: Canonical  
Audience: Operators, reviewers, and technical users

This guide explains how to use theFactory through Mission Control for the main operator workflows.

## Primary Screens

- `Home`
  - runtime summary and launch overview
- `Chat`
  - PM-style mission intake from a prompt and attachments
- `Missions`
  - mission list, state, and navigation to mission detail
- `Agents`
  - 38-agent runtime topology and persona drill-down
- `LogicNodes`
  - extracted mission-linked graph fragments
- `Semantic Bus`
  - event and protocol traffic inspection
- `Databases`
  - data-plane readiness and adapter status
- `Repo Import`
  - grounded GitHub review and mission launch flow
- `Settings`
  - preferences, vault slots, and integration state

## Common Operator Workflows

### Launch a mission from Chat

1. Open `Chat`.
2. Enter the mission request and add any supporting files.
3. Review the inferred target language.
4. Launch the mission.
5. Open the created mission in `Missions` to watch progression.

### Launch a mission from Builder review

1. Open `Builder`.
2. Select the local files to ground the review.
3. Review the generated patch contract and fingerprint.
4. Approve the review.
5. Launch the mission bundle.

### Launch a mission from Repo Import

1. Open `Repo Import`.
2. Select the repository and files to review.
3. Confirm the generated review summary and fingerprint.
4. Approve the review.
5. Launch the mission bundle.

## Reviewing Mission State

Use the mission detail page to inspect:

- mission phase stepper
- route provenance
- mission event log
- build artifacts
- logicnode and related runtime evidence

Source-bundle missions should not be treated as release-ready until the `Build Artifacts` section shows successful packaging.

## Secrets and Integrations

Use `Settings` to:

- load provider credentials
- validate vault-backed slots
- confirm GitHub integration state

Review approvals depend on Mission Control being configured with:

- `ORCHESTRATOR_INTERNAL_BASE_URL`
- `INTERNAL_SERVICE_API_KEY`

## Troubleshooting

- If data panels fail to load, check the gateway health endpoint.
- If live mission updates stall, verify the gateway SSE endpoint.
- If review approvals fail, verify the internal orchestrator URL and service key.
- If a mission remains `VERIFIED`, inspect the build artifact state before treating it as complete.

## Related References

- [GETTING_STARTED.md](GETTING_STARTED.md)
- [../API_INTEGRATION_GUIDE.md](../API_INTEGRATION_GUIDE.md)
- [../ARCHITECTURE.md](../ARCHITECTURE.md)
- [../OPERATIONS_RUNBOOK.md](../OPERATIONS_RUNBOOK.md)
