SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

BACKEND_DIR := backend
FRONTEND_DIR := frontend
UV ?= uv
NPM ?= npm
DOCKER_COMPOSE ?= docker compose

.PHONY: help setup backend-install frontend-install migrate dev-backend dev-frontend \
	test test-backend test-frontend lint typecheck build-frontend openapi \
	docker-up docker-down check-all

help: ## Show available targets and descriptions
	@echo "Spotter — Weather-Aware Truck Routing"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Bootstrap local .env (if missing), install backend & frontend deps, and run migrations
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example (fixture mode by default; never commit .env)."; \
	fi
	$(MAKE) backend-install
	$(MAKE) frontend-install
	$(MAKE) migrate

backend-install: ## Install backend Python dependencies via uv
	cd $(BACKEND_DIR) && $(UV) sync --all-extras

frontend-install: ## Install frontend Node dependencies via npm
	cd $(FRONTEND_DIR) && if [ -f package-lock.json ]; then $(NPM) ci; else $(NPM) install; fi

migrate: ## Run Django database migrations
	cd $(BACKEND_DIR) && $(UV) run python manage.py migrate

dev-backend: ## Start Django development server on http://localhost:8000
	cd $(BACKEND_DIR) && $(UV) run python manage.py runserver 0.0.0.0:8000

dev-frontend: ## Start Vite development server on http://localhost:5173
	cd $(FRONTEND_DIR) && $(NPM) run dev

test-backend: ## Run backend pytest test suite
	cd $(BACKEND_DIR) && $(UV) run pytest -v

test-frontend: ## Run frontend Vitest unit/component test suite once
	cd $(FRONTEND_DIR) && $(NPM) run test -- --run

test: test-backend test-frontend ## Run all backend and frontend tests

lint: ## Run backend (ruff) and frontend (eslint) linters
	cd $(BACKEND_DIR) && $(UV) run ruff check .
	cd $(FRONTEND_DIR) && $(NPM) run lint

typecheck: ## Run backend (mypy) and frontend (tsc) type checks
	cd $(BACKEND_DIR) && $(UV) run mypy .
	cd $(FRONTEND_DIR) && $(NPM) run typecheck

build-frontend: ## Build production frontend bundle
	cd $(FRONTEND_DIR) && $(NPM) run build

openapi: ## Export OpenAPI 3 schema from Django REST Framework to backend/openapi.yaml
	cd $(BACKEND_DIR) && $(UV) run python manage.py spectacular --file openapi.yaml
	@echo "Exported OpenAPI schema to $(BACKEND_DIR)/openapi.yaml"

docker-up: ## Build and start full stack via Docker Compose (set COMPOSE_PROFILES=async for Celery worker)
	$(DOCKER_COMPOSE) up --build -d

docker-down: ## Stop and remove Docker Compose containers (including async profile)
	$(DOCKER_COMPOSE) --profile async down

check-all: lint typecheck ## Run full local CI verification suite (lint, typecheck, Django checks, tests, build)
	cd $(BACKEND_DIR) && $(UV) run python manage.py check
	cd $(BACKEND_DIR) && $(UV) run python manage.py makemigrations --check --dry-run
	$(MAKE) test
	$(MAKE) build-frontend
