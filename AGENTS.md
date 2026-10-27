# crowspeak-core

Python engine (`crowspeak_engine`), reference CLI (`crowspeak_cli`) and design docs. See `docs/engine-design.md`.

## Setup

`uv sync` alone installs only the engine's base dependency (`openai`) and removes anything else, so name the dependency groups you need: `uv sync --group cli --group dev` (what CI uses), plus `--group tui` for the TUI. These are PEP 735 groups, not published extras. `python-dotenv` is in `cli`; `pytest`, `ruff`, `mypy` and `bandit` are in `dev`. A later plain `uv sync` or `uv run` re-syncs without them, so pass `--group` to `uv run` too (for example `uv run --group cli python -m crowspeak_cli`). The CLI is not part of the published wheel, so there is no `crowspeak-cli` command. Run it with `make cli` (against the engine built as a wheel, the default for checking the package) or `make cli-dev` (against `src/`, for engine work); `--debug` prints which engine is in use. Its saved profile is `src/crowspeak_cli/learner.json` (gitignored); `--reset` re-runs setup, `--profile PATH` picks another file. As always, set `LLM_PROVIDER=local` unless you mean to use Azure.

## Testing policy

- **Default tests must not touch the network.** Unit tests use `FakeLLM` (`tests/conftest.py`). Functional/wiring tests against a real model use the local provider: run Ollama and set `LLM_PROVIDER=local` (see `.env.example`).
- **Live Azure Foundry tests are opt-in.** Mark them `@pytest.mark.live` (or `pytestmark = pytest.mark.live`). They are deselected by default (`addopts = "-m 'not live'"`) and run only with `pytest -m live`. They cost real Azure spend on the user's own API key, so use them only for model quality/latency evaluation.
- **Do not run live tests or the CLI with `LLM_PROVIDER=azure` casually**, whether you are a person or an agent. Agents must ask the user first. The same applies to a per-job override such as `LLM_CORRECTIONS_PROVIDER=azure`, even when the default provider is local.

## Typing

The wheel ships `py.typed`, so `uv run --group dev mypy` (config in `pyproject.toml`, scope `src/crowspeak_engine`) must stay clean and CI enforces it. Fix findings by making the types say what the code guarantees; avoid `# type: ignore` (unused ones are flagged).

## Boundaries

- The engine never reads the environment or does terminal I/O. Only `llm/factory.py` may read env vars (`tests/test_boundary.py` enforces this).
- Provider config is explicit first: adapters, or `ProviderConfig` with `build_provider()` / `providers_from_config()`. `provider_from_env()` and `providers_from_env()` in `crowspeak_engine.llm` are convenience mappers for the CLI, tests and local development. Keep `Session` and prompt logic provider-agnostic.
