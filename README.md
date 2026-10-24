# crowspeak-engine

UI-agnostic conversation engine for CrowSpeak language practice. The engine takes learner
input and yields events; it does no terminal I/O and reads no environment variables itself.
See [docs/engine-design.md](docs/engine-design.md) for the design.

## Install

```
pip install crowspeak-engine
```

Requires Python 3.10 or newer.

## Reference CLI

The CLI lives in this repo and is not part of the published package. It runs two ways:

```
make cli ARGS="--debug"       # against the engine built as a wheel: what a consumer installs
make cli-dev ARGS="--debug"   # against the engine source in src/: for iterating on the engine
make cli-testpypi VERSION=0.1.0   # against a build published to TestPyPI
```

`--debug` prints which engine is in use (a `site-packages` path, or this repo's `src/`).
Installed mode builds a throwaway venv on every run, so it takes a few seconds longer.

The first run asks a few setup questions and saves them to `src/crowspeak_cli/learner.json`
(gitignored, plain JSON you can read and edit). Later runs load it. Use `--reset` to run setup
again and `--profile PATH` to use another file.

Configure a provider with environment variables; see `.env.example`. The default provider
is Azure AI Foundry using your own endpoint and key. A local OpenAI-compatible server such as
Ollama also works (`LLM_PROVIDER=local`).

## Development

```
uv sync --group cli --group dev
uv run --group cli --group dev pytest
```

Tests do not touch the network by default. See [AGENTS.md](AGENTS.md) for the testing policy.

## License

Apache License 2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Model and provider services you connect to (Azure OpenAI, local models such as Gemma via
Ollama, and so on) are governed by their own terms, which are your responsibility.
