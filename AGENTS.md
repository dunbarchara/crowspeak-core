# crowspeak-core

Python engine (`crowspeak_engine`), reference CLI (`crowspeak_cli`) and design docs. See `docs/engine-design.md`.

## Testing policy

- **Default tests must not touch the network.** Unit tests use `FakeLLM` (`tests/conftest.py`). Functional/wiring tests against a real model use the local provider: run Ollama and set `LLM_PROVIDER=local` (see `.env.example`).
- **Live Azure Foundry tests are opt-in.** Mark them `@pytest.mark.live` (or `pytestmark = pytest.mark.live`). They are deselected by default (`addopts = "-m 'not live'"`) and run only with `pytest -m live`. They cost real Azure spend on the user's own API key, so use them only for model quality/latency evaluation.
- **Do not run live tests or the CLI with `LLM_PROVIDER=azure` casually**, whether you are a person or an agent. Agents must ask the user first.

## Boundaries

- The engine never reads the environment or does terminal I/O. Only the `llm/` adapters and factory may read env vars (`tests/test_boundary.py` enforces this).
- Provider selection goes through `crowspeak_engine.llm.provider_from_env()`. Keep `Session` and prompt logic provider-agnostic.
