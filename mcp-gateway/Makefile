.PHONY: setup dev run stop down logs lint format typecheck test check migrate seed

setup:
	python -m app.core.setup

dev: setup
	docker compose up --build -d
	docker compose exec -T api alembic upgrade head
	docker compose exec -T api python -m app.db.seeds

run: dev
	docker compose logs -f api

down:
	docker compose down

stop: down

logs:
	docker compose logs -f

lint:
	ruff check .

format:
	ruff format app tests

typecheck:
	mypy app

test:
	pytest

check: lint typecheck test

migrate:
	docker compose exec -T api alembic upgrade head

seed:
	docker compose exec -T api python -m app.db.seeds

