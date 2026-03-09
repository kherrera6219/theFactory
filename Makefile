.PHONY: up down up-full-dedicated down-full-dedicated validate lint test test-ui test-ui-e2e test-fast test-live-extended audit promotion-gate qualification-summary dora-metrics compose-validate sweep openapi predeploy backup dr perf reliability langgraph-recovery dedicated-canary dedicated-canary-trend oidc-matrix langgraph-v2-prototype monitor-up monitor-down agent-keys

up:
	docker compose -f deploy/docker-compose.yaml up -d --build

down:
	docker compose -f deploy/docker-compose.yaml down -v

up-full-dedicated:
	docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents up -d --build \
		redis postgres qdrant jaeger orchestrator api-gateway semantic-bus-mcp audit-worker dashboard mission-control \
		pod-a-dedicated-mgr-worker pod-b-dedicated-mgr-worker pod-c-dedicated-mgr-worker pod-d-dedicated-mgr-worker \
		agent-01-pm agent-02-ceo agent-03-broker agent-04-accountant agent-05-security agent-06-is agent-07-vc agent-08-compliance agent-09-hw agent-10-tester agent-11-deploy \
		agent-13-poda-audit agent-19-podb-audit agent-25-podc-audit agent-31-podd-audit \
		agent-14-python agent-15-javascript agent-16-ruby agent-17-php \
		agent-20-c agent-21-cpp agent-22-rust agent-23-zig \
		agent-26-java agent-27-csharp agent-28-scala agent-29-kotlin \
		agent-32-matlab agent-33-r agent-34-julia agent-35-mathematica

down-full-dedicated:
	docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents down -v

monitor-up:
	docker compose -f deploy/docker-compose.monitoring.yaml up -d

monitor-down:
	docker compose -f deploy/docker-compose.monitoring.yaml down -v

validate:
	python scripts/validate_schemas.py
	python scripts/build_refined_ir_catalog.py

lint:
	ruff check services tests scripts

test:
	pytest --cov=services --cov-report=term-missing --cov-report=xml --cov-fail-under=80
	python scripts/check_coverage_thresholds.py \
		--coverage-file coverage.xml \
		--global-threshold 80 \
		--module-threshold services/pod-worker/pod_worker/main.py=100 \
		--module-threshold services/audit-worker/audit_worker/main.py=100 \
		--module-threshold services/semantic-bus-mcp/semantic_bus/mcp_server.py=100 \
		--module-threshold services/orchestrator/orchestrator/protocol.py=100 \
		--module-threshold services/orchestrator/orchestrator/runtime.py=100 \
		--module-threshold services/orchestrator/orchestrator/agent_personas.py=100 \
		--module-threshold services/orchestrator/orchestrator/agent_integrations.py=100 \
		--module-threshold services/orchestrator/orchestrator/agent_registry.py=100

test-ui:
	cd apps/mission-control && npm run lint && npm run test

test-ui-e2e:
	cd apps/mission-control && npm run test:e2e

test-fast:
	pytest

test-live-extended:
	pytest -q tests/services/test_live_extended_data_plane_integration.py

audit:
	python scripts/production_review_audit.py

promotion-gate:
	python scripts/export_agent_model_inventory.py \
		--output-file reports/agent-model-inventory.local.json
	python scripts/qualification_gate_summary.py \
		--policy-file deploy/promotion-policy.json \
		--output-file reports/qualification-gate-summary.local.json
	python scripts/promotion_gate.py \
		--policy-file deploy/promotion-policy.json \
		--ref refs/heads/main \
		--ci-status success \
		--attestation-verified true \
		--signed-tag-verified false \
		--model-inventory-file reports/agent-model-inventory.local.json \
		--qualification-summary-file reports/qualification-gate-summary.local.json \
		--output-file reports/promotion-decision.local.json

qualification-summary:
	python scripts/qualification_gate_summary.py \
		--policy-file deploy/promotion-policy.json \
		--output-file docs/evidence/qualification_gate_summary_latest.json

dora-metrics:
	python scripts/dora_metrics_summary.py \
		--output-file docs/evidence/dora_metrics_latest.json

agent-keys:
	python scripts/generate_agent_service_keys.py

compose-validate:
	docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.dev.yaml config
	docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.staging.yaml config
	docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.prod.yaml config
	docker compose -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml config

openapi:
	python scripts/export_openapi.py

predeploy:
	powershell -ExecutionPolicy Bypass -File scripts/pre_deploy_check.ps1

backup:
	powershell -ExecutionPolicy Bypass -File scripts/backup_postgres.ps1

dr:
	powershell -ExecutionPolicy Bypass -File scripts/dr_drill.ps1

perf:
	powershell -ExecutionPolicy Bypass -File scripts/perf_smoke.ps1

reliability:
	powershell -ExecutionPolicy Bypass -File scripts/reliability_qualification.ps1

langgraph-recovery:
	powershell -ExecutionPolicy Bypass -File scripts/langgraph_postgres_recovery_qualification.ps1

dedicated-canary:
	powershell -ExecutionPolicy Bypass -File scripts/dedicated_agent_canary_rollout.ps1

dedicated-canary-trend:
	powershell -ExecutionPolicy Bypass -File scripts/dedicated_agent_canary_trend.ps1

oidc-matrix:
	powershell -ExecutionPolicy Bypass -File scripts/operator_route_auth_matrix_qualification.ps1

langgraph-v2-prototype:
	powershell -ExecutionPolicy Bypass -File scripts/langgraph_v2_prototype_matrix.ps1

sweep:
	powershell -ExecutionPolicy Bypass -File scripts/debug_sweep.ps1
