# Canonical Deployment Target:
# Local Development: docker-compose.yml (Canonical dev target, ports 8000 API, 3000 Frontend, 9090 Prometheus)
# Production Deployment: Kubernetes (k8s/) (Canonical prod target, matching port mappings and env variables)

.PHONY: help install dev test lint sec-scan clean hooks

help: ## Display this help message
	@echo "Available Sarthi targets:"
	@echo "  install   - Install Python dependencies"
	@echo "  dev       - Run canonical dev environment via docker-compose"
	@echo "  test      - Run test suite with pytest"
	@echo "  lint      - Run linter checks with ruff"
	@echo "  sec-scan  - Run security scans with gitleaks and ruff"
	@echo "  clean     - Remove cache and artifact files"

hooks:
	pre-commit install

install:
	pip install -r backend/requirements.txt

dev:
	docker-compose up --build

test:
	pytest

lint:
	ruff check backend/

sec-scan:
	gitleaks detect --no-git || true
	ruff check backend/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
