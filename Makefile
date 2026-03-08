.PHONY: up down validate lint test test-ui test-ui-e2e test-fast test-live-extended audit promotion-gate sweep openapi predeploy backup dr perf reliability langgraph-recovery dedicated-canary dedicated-canary-trend oidc-matrix langgraph-v2-prototype monitor-up monitor-down

up:
	docker compose -f deploy/docker-compose.yaml up -d --build

down:
	docker compose -f deploy/docker-compose.yaml down -v

monitor-up:
	docker compose -f deploy/docker-compose.monitoring.yaml up -d

monitor-down:
	docker compose -f deploy/docker-compose.monitoring.yaml down -v

validate:
	python scripts/validate_schemas.py

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
	python scripts/promotion_gate.py \
		--policy-file deploy/promotion-policy.json \
		--ref refs/heads/main \
		--ci-status success \
		--attestation-verified true \
		--output-file reports/promotion-decision.local.json

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
