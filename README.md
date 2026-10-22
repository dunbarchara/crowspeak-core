# crowspeak-engine

UI-agnostic conversation engine for CrowSpeak language practice. The engine takes learner
input and yields events; it does no terminal I/O and reads no environment variables itself.
See [docs/engine-design.md](docs/engine-design.md) for the design.

## Install

```
pip install crowspeak-engine
pip install "crowspeak-engine[cli]"   # adds the reference CLI dependencies
```

Requires Python 3.10 or newer.

## Reference CLI

```
crowspeak-cli
```

Configure a provider with environment variables; see `.env.example`. The default provider
is Azure AI Foundry using your own endpoint and key. A local OpenAI-compatible server such as
Ollama also works (`LLM_PROVIDER=local`).

## Development

```
uv sync --extra cli --extra dev
uv run --extra cli --extra dev pytest
```

Tests do not touch the network by default. See [AGENTS.md](AGENTS.md) for the testing policy.

## License

Apache License 2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Model and provider services you connect to (Azure OpenAI, local models such as Gemma via
Ollama, and so on) are governed by their own terms, which are your responsibility.
