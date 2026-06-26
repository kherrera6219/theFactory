
.PHONY: check-env force-stop
check-env:
	@python scripts/check_env.py

force-stop:
	@python scripts/force_stop.py

.PHONY: check-env up down up-full-dedicated down-full-dedicated validate lint test test-ui test-ui-e2e test-fast test-live-extended eval-ai demo audit promotion-gate release-evidence-verify qualification-summary dora-metrics compose-validate sweep openapi predeploy backup backup-verify dr dr-ps1 perf reliability langgraph-recovery dedicated-canary dedicated-canary-trend oidc-matrix langgraph-v2-prototype monitor-up monitor-down agent-keys tls-certs prune-audit
# validate: full pre-merge gate — lint + schema check + pytest + UI lint/test

up: check-env tls-certs
	docker compose --env-file .env -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents up -d --build \
		redis postgres pgbouncer qdrant minio milvus neo4j jaeger orchestrator api-gateway protocol-bus-mcp audit-worker dashboard mission-control \
		pod-a-dedicated-mgr-worker pod-b-dedicated-mgr-worker pod-c-dedicated-mgr-worker pod-d-dedicated-mgr-worker \
		agent-01-pm agent-02-ceo agent-03-broker agent-04-accountant agent-05-security agent-06-is agent-07-vc agent-08-compliance agent-09-hw agent-10-tester agent-11-deploy \
		agent-13-poda-audit agent-19-podb-audit agent-25-podc-audit agent-31-podd-audit \
		agent-14-python agent-15-javascript agent-16-ruby agent-17-php \
		agent-20-c agent-21-cpp agent-22-rust agent-23-zig agent-36-go \
		agent-26-java agent-27-csharp agent-28-scala agent-29-kotlin \
		agent-32-matlab agent-33-r agent-34-julia agent-35-mathematica agent-37-haskell agent-38-ocaml \
		agent-39-depabs agent-40-testdata agent-41-rqca

down:
	docker compose --env-file .env -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents down -v

up-full-dedicated: up
down-full-dedicated: down

up-condensed: check-env tls-certs
	docker compose --env-file .env -f deploy/docker-compose.yaml up -d --build

down-condensed:
	docker compose --env-file .env -f deploy/docker-compose.yaml down -v

monitor-up:
	docker compose -f deploy/docker-compose.monitoring.yaml up -d

monitor-down:
	docker compose -f deploy/docker-compose.monitoring.yaml down -v

validate:
	ruff check services tests scripts
	python scripts/validate_documentation.py
	python scripts/export_openapi.py --check
	python scripts/validate_schemas.py
	python scripts/build_refined_ir_catalog.py
	pytest --tb=short -q
	cd apps/mission-control && npm run lint && npm run test

lint:
	ruff check services tests scripts

test:
	pytest --cov=services --cov-report=term-missing --cov-report=xml --cov-fail-under=80
	python scripts/check_coverage_thresholds.py \
		--coverage-file coverage.xml \
		--global-threshold 80 \
		--module-threshold services/pod-worker/pod_worker/main.py=80 \
		--module-threshold services/audit-worker/audit_worker/main.py=90 \
		--module-threshold services/protocol-bus-mcp/protocol_bus/mcp_server.py=100 \
		--module-threshold services/orchestrator/orchestrator/protocol.py=100 \
		--module-threshold services/orchestrator/orchestrator/runtime.py=80 \
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

eval-ai:
	pytest -q tests/eval/test_llm_delegation_golden.py

eval:
	pytest tests/eval/ -v --tb=short -x \
		-m "not live_llm" \
		--no-header

demo:
	python scripts/demo_missions.py --dry-run \
		--output-file docs/evidence/phase18_demo_missions_latest.json

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

release-evidence-verify:
	python scripts/verify_release_evidence.py \
		--release-manifest-file reports/release-manifest.json \
		--attestation-verification-file reports/attestation-verification.txt \
		--promotion-decision-file reports/promotion-decision.json

qualification-summary:
	python scripts/qualification_gate_summary.py \
		--policy-file deploy/promotion-policy.json \
		--output-file docs/evidence/qualification_gate_summary_latest.json

dora-metrics:
	python scripts/dora_metrics_summary.py \
		--output-file docs/evidence/dora_metrics_latest.json

agent-keys:
	python scripts/generate_agent_service_keys.py

prune-audit:
	python scripts/prune_audit_tables.py $(if $(RETENTION_DAYS),--retention-days $(RETENTION_DAYS),)

tls-certs:
	powershell -ExecutionPolicy Bypass -File scripts/generate_dev_tls_certs.ps1

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

backup-verify:
ifndef BACKUP_FILE
	$(error BACKUP_FILE is required, for example BACKUP_FILE=backups/ulr_20260329_000000.sql)
endif
ifndef MANIFEST_FILE
	$(error MANIFEST_FILE is required, for example MANIFEST_FILE=backups/ulr_20260329_000000.sql.json)
endif
	python scripts/verify_backup_artifacts.py \
		--backup-file "$(BACKUP_FILE)" \
		--manifest-file "$(MANIFEST_FILE)" \
		--output-file reports/backup-verification.local.json

dr:
	python scripts/run_automated_dr_drill.py $(if $(DRY_RUN),--dry-run,)

dr-ps1:
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

demo:
	python scripts/run_demo_mission.py

demo-js:
	python scripts/run_demo_mission.py --language javascript

demo-ts:
	python scripts/run_demo_mission.py --language typescript

demo-check:
	python scripts/run_demo_mission.py --dry-run
