.PHONY: up down fmt validate

up:
	docker compose -f deploy/docker-compose.yaml up -d --build

down:
	docker compose -f deploy/docker-compose.yaml down -v

validate:
	python3 scripts/validate_schemas.py

fmt:
	python3 -m pip install -q ruff || true
	ruff format services || true
