# Local mirror of the CI jobs in .github/workflows/ci.yml.
# CI is still the source of truth; these targets just let you catch failures before pushing.
#
# Usage:
#   make install           # one-time: sync deps + install git hooks
#   make check             # everything CI runs
#   make check-pre-commit  # hooks only (gitleaks, ruff, hygiene)
#   make check-python      # ruff, mypy, bandit, pytest, pip-audit
#   make check-build       # build the wheel + sdist and verify their contents
#   make cli ARGS="..."    # run the CLI against the engine built as a wheel (installed mode)
#   make cli-dev ARGS="..." # run the CLI against the engine source in src/ (for iterating)
#   make cli-testpypi VERSION=0.1.0 ARGS="..."  # CLI against a published TestPyPI build
#
# Prerequisites: uv, pre-commit.

ifeq ($(OS),Windows_NT)
SHELL := C:/Program Files/Git/bin/bash.exe
endif

.PHONY: install check check-pre-commit check-python check-build cli cli-installed cli-dev cli-testpypi

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
	@echo "── mypy ──"
	uv run mypy
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

# ─── cli ──────────────────────────────────────────────────────────────────────
# Installed mode (default) builds the wheel into a throwaway venv, so it tests the package
# a consumer would get. Dev mode uses the repo source. `--debug` prints which engine is used.
# Providers come from .env; use LLM_PROVIDER=local unless you mean to spend Azure money.
cli: cli-installed

cli-installed:
	python scripts/cli_installed.py -- $(ARGS)

cli-dev:
	uv run --group cli python -m crowspeak_cli $(ARGS)

cli-testpypi:
	python scripts/cli_installed.py --index testpypi $(if $(VERSION),--version $(VERSION)) -- $(ARGS)
