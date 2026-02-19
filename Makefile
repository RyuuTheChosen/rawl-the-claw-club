.PHONY: help dev up down migrate test lint fmt

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Start Docker services (PostgreSQL, Redis, MinIO)
	docker compose up -d

down: ## Stop Docker services
	docker compose down

migrate: ## Run Alembic migrations
	cd packages/backend && alembic upgrade head

test: ## Run all backend tests
	cd packages/backend && pytest -v

test-adapters: ## Run game adapter tests
	cd packages/backend && pytest tests/test_game_adapters/ -v

test-engine: ## Run engine tests
	cd packages/backend && pytest tests/test_engine/ -v

lint: ## Lint backend code
	cd packages/backend && ruff check src/

fmt: ## Format backend code
	cd packages/backend && ruff format src/

dev-backend: ## Start backend dev server
	cd packages/backend && uvicorn rawl.main:create_app --factory --reload --host 0.0.0.0 --port 8080

dev-frontend: ## Start frontend dev server
	cd packages/frontend && npm run dev

dev-worker: ## Start Celery worker
	cd packages/backend && celery -A rawl.celery_app worker --loglevel=info

dev-beat: ## Start Celery beat scheduler
	cd packages/backend && celery -A rawl.celery_app beat --loglevel=info

contracts-install: ## Install Foundry contract dependencies
	cd packages/contracts && forge install foundry-rs/forge-std OpenZeppelin/openzeppelin-contracts@v5.1.0 --no-git

contracts-build: ## Build Foundry contracts
	cd packages/contracts && forge build --sizes

contracts-test: ## Test Foundry contracts
	cd packages/contracts && forge test -vvv

contracts-test-fuzz: ## Fuzz test contracts (5000 runs)
	cd packages/contracts && forge test --fuzz-runs 5000 --match-contract Fuzz -vvv

contracts-snapshot: ## Gas snapshot for contracts
	cd packages/contracts && forge snapshot

contracts-deploy-sepolia: ## Deploy contracts to Base Sepolia
	cd packages/contracts && forge script script/Deploy.s.sol --rpc-url $$BASE_SEPOLIA_RPC --broadcast --verify
