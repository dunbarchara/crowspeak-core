# Local mirror of the CI jobs in .github/workflows/ci.yml.
# CI is still the source of truth; these targets just let you catch failures before pushing.
#
# Usage:
#   make install           # one-time: sync deps + install git hooks
#   make check             # everything CI runs
#   make check-pre-commit  # hooks only (gitleaks, ruff, hygiene)
#   make check-python      # ruff, bandit, pytest, pip-audit
#   make check-build       # build the wheel + sdist and verify their contents
#
# Prerequisites: uv, pre-commit.

ifeq ($(OS),Windows_NT)
SHELL := C:/Program Files/Git/bin/bash.exe
endif

.PHONY: install check check-pre-commit check-python check-build

install:
	uv sync --frozen --group dev --group cli
	pre-commit install

check: check-pre-commit check-python check-build

# ─── pre-commit ───────────────────────────────────────────────────────────────
check-pre-commit:
	pre-commit run --all-files

# ─── python ───────────────────────────────────────────────────────────────────
# Live (Azure) tests are deselected by default; they cost money. See AGENTS.md.
check-python:
	@echo "── ruff ──"
	uv run ruff check .
	@echo "── bandit ──"
	uv run bandit -r src -ll -q
	@echo "── pytest ──"
	uv run pytest
	@echo "── pip-audit ──"
	uv run pip-audit

# ─── build ────────────────────────────────────────────────────────────────────
# Builds and inspects the artifacts; the clean-venv install test runs in CI only.
check-build:
	rm -rf dist
	uv build
	uvx twine==7.0.0 check --strict dist/*
	python scripts/check_dist.py dist
