.PHONY: up down test check seed

up:
	docker compose up --build -d

down:
	docker compose down

test:
	uv run --locked pytest --cov=src --cov-branch --cov-fail-under=95

check: test
	uv run --locked ruff check .
	uv run --locked mypy src tests

seed:
	docker compose exec -T app python -m infrastructure.seed < tests/fixtures/demo_inventory.json
