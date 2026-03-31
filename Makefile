.PHONY: help dev up down logs migrate seed lint test deploy db-shell redis-cli

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: up migrate ## Start dev environment (up + migrate)

up: ## Start all services
	docker compose up -d --build

down: ## Stop all services
	docker compose down

logs: ## Tail bot logs
	docker compose logs -f bot

migrate: ## Run database migrations
	docker compose exec bot python -m bot.migrate

seed: ## Seed test data
	docker compose exec bot python -m db.seed

lint: ## Run linters (ruff + mypy)
	docker compose exec bot ruff check bot/
	docker compose exec bot mypy bot/ --ignore-missing-imports

test: ## Run tests
	docker compose exec bot pytest tests/ -v

deploy: ## Deploy to production (Timeweb VPS)
	ssh personalai 'cd /opt/personalai && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build && docker compose -f docker-compose.prod.yml exec -T bot python -m bot.migrate'

db-shell: ## Open psql shell
	docker compose exec db psql -U personalai -d personalai

redis-cli: ## Open Redis CLI
	docker compose exec redis redis-cli
