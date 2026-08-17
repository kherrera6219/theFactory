# Mission Control Operator Guide

Document version: 2026.08.17  
Last updated: 2026-08-17  
Status: Canonical  
Audience: Operators, reviewers, and technical users

This guide explains how to use theFactory through Mission Control for the main operator workflows.

## Primary Screens

- `Home`
  - runtime summary and launch overview
- `Chat`
  - PM-led Statement of Work: create, import, port, or update; review factory cost range + cap; Accept SOW before start
- `Missions`
  - mission list, state, and navigation to mission detail
- `Projects`
  - per-project audit timeline across missions and agents
- `Agents`
  - 41-agent runtime topology and persona drill-down
- `LogicNodes`
  - extracted mission-linked graph fragments
- `Protocol Bus`
  - event and protocol traffic inspection
  - Live protocol message stream with `stream|poll|paused` transport diagnostics. Messages returning 409 indicate replay detection (expected); 503 indicates Redis unavailability.
- `Databases`
  - data-plane readiness and adapter status
- `Builder`
  - grounded local-workspace review and mission launch flow
- `Repo Import`
  - grounded GitHub review and mission launch flow
- `Settings`
  - preferences, vault slots, and integration state

## Common Operator Workflows

### Unlock Mission Control

1. Open Mission Control.
2. Enter `MISSION_CONTROL_ADMIN_KEY` on the unlock screen.
3. Continue into the shell once the operator session is established.

### Launch a mission from Chat

1. Open `Chat`.
2. Enter the request. Attach a ZIP to import, port, or update existing software.
3. Review the SOW panel: out of scope, deliverables, and factory cost range + cap.
4. Accept the SOW. That is the bid, not "start anyway."
5. Open the created mission in `Missions`. A FAIL QC verdict does not become `COMPLETE`.

### Launch a mission from Builder review

1. Open `Builder`.
2. Select the local files to ground the review.
3. Review the generated patch contract and fingerprint.
4. Approve the review.
5. Launch the mission bundle after Mission Control verifies the stored approval receipt.

### Launch a mission from Repo Import

1. Open `Repo Import`.
2. Select the repository and files to review.
3. Confirm the generated review summary and fingerprint.
4. Approve the review.
5. Launch the mission bundle after Mission Control verifies the stored approval receipt.

## Reviewing Mission State

Use the mission detail page to inspect:

- mission phase stepper
- route provenance
- mission event log
- build artifacts
- logicnode and related runtime evidence

Source-bundle missions should not be treated as release-ready until the `Build Artifacts` section shows successful packaging.

## Reviewing Project Audit History

Use `Projects` when you need to answer:

- which agents touched a project
- what each agent wrote or persisted
- which tool or HTTP path was used
- when an execution started, completed, or failed

The project audit timeline is backed by append-only orchestrator audit events. Each row is keyed by `project_id` and includes the related mission, agent, service, object type, tool name, and execution duration when available.

## Secrets and Integrations

Use `Settings` to:

- load provider credentials
- validate vault-backed slots
- confirm GitHub integration state

Review approvals depend on Mission Control being configured with:

- `MISSION_CONTROL_ADMIN_KEY`
- `MISSION_CONTROL_SESSION_SECRET`
- `ORCHESTRATOR_INTERNAL_BASE_URL`
- `INTERNAL_SERVICE_API_KEY`
- `APPROVAL_HMAC_SECRET`

For browser-based operator workflows, Mission Control uses the signed operator session cookie rather than trusting origin or referrer headers. For scripted vault administration, `/api/vault` also accepts `x-vault-admin-key` when `VAULT_ADMIN_KEY` is configured.

## Troubleshooting

- If data panels fail to load, check the gateway health endpoint.
- If live mission updates stall, verify the gateway SSE endpoint.
- If the unlock screen rejects a valid-looking key, verify `MISSION_CONTROL_ADMIN_KEY` and `MISSION_CONTROL_SESSION_SECRET`.
- If review approvals fail, verify the internal orchestrator URL, service key, and approval HMAC secret.
- If a mission remains `VERIFIED`, inspect the build artifact state before treating it as complete.

## Related References

- [GETTING_STARTED.md](GETTING_STARTED.md)
- [../API_INTEGRATION_GUIDE.md](../API_INTEGRATION_GUIDE.md)
- [../ARCHITECTURE.md](../ARCHITECTURE.md)
- [../OPERATIONS_RUNBOOK.md](../OPERATIONS_RUNBOOK.md)
