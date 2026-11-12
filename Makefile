BACKEND := backend
FRONTEND := frontend
VENV := $(BACKEND)/.venv
PY := $(VENV)/bin/python

.PHONY: help install dev backend frontend test lint format build docker up down clean admin

help:
	@echo "install   Install backend and frontend dependencies"
	@echo "dev       Run the API and the web client together"
	@echo "backend   Run the API only"
	@echo "frontend  Run the web client only"
	@echo "test      Run the backend and frontend test suites"
	@echo "lint      Run ruff, eslint and the type checker"
	@echo "build     Build the production frontend bundle"
	@echo "docker    Build and start the stack with compose"
	@echo "admin     Create or promote an administrator account"

install:
	cd $(BACKEND) && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
	cd $(FRONTEND) && npm install

backend:
	cd $(BACKEND) && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	cd $(FRONTEND) && npm run dev

dev:
	@echo "Run 'make backend' and 'make frontend' in two terminals."

test:
	cd $(BACKEND) && .venv/bin/pytest
	cd $(FRONTEND) && npm test

lint:
	cd $(BACKEND) && .venv/bin/ruff check .
	cd $(FRONTEND) && npm run lint && npm run typecheck

format:
	cd $(BACKEND) && .venv/bin/ruff check . --fix
	cd $(FRONTEND) && npm run lint -- --fix

build:
	cd $(FRONTEND) && npm run build

docker:
	docker compose up --build

up: docker

down:
	docker compose down

admin:
	cd $(BACKEND) && .venv/bin/python -m app.cli create-admin --email "$(EMAIL)" --password "$(PASSWORD)"

clean:
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.ruff_cache $(BACKEND)/coverage.xml $(FRONTEND)/dist
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
