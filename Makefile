.PHONY: up down validate lint test test-fast audit sweep openapi predeploy backup dr perf monitor-up monitor-down

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

test-fast:
	pytest

audit:
	python scripts/production_review_audit.py

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

sweep:
	powershell -ExecutionPolicy Bypass -File scripts/debug_sweep.ps1
