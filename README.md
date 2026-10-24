# crowspeak-engine

UI-agnostic conversation engine for CrowSpeak language practice. The engine takes learner
input and yields events; it does no terminal I/O and reads no environment variables itself.
See [docs/engine-design.md](docs/engine-design.md) for the design.

## Install

```
pip install crowspeak-engine
```

Requires Python 3.10 or newer. The only runtime dependency is `openai`.

Until the first release is on PyPI, install a development build instead:

```
# a pre-release build from TestPyPI (openai comes from the real index)
pip install --index-url https://test.pypi.org/simple/     --extra-index-url https://pypi.org/simple/ crowspeak-engine==0.1.0

# or straight from git, pinned to a tag or commit
pip install "crowspeak-engine @ git+https://github.com/dunbarchara/crowspeak-core@<tag-or-sha>"
```

In `pyproject.toml` the git form is `"crowspeak-engine @ git+https://github.com/dunbarchara/crowspeak-core@<tag-or-sha>"`
under `dependencies`. Pin an exact version (`crowspeak-engine==x.y.z`); while the version is 0.x a
minor release may change the public API ([stability policy](docs/engine-design.md)).

## Using the engine

```python
import asyncio

from crowspeak_engine import (
    Engine, LanguageProfile, Learner, Proficiency, ProviderConfig, Providers, Target,
    TranscriptDelta, build_provider,
)

provider = build_provider(ProviderConfig(kind="local"))  # any OpenAI-compatible server
engine = Engine(providers=Providers(default=provider))
learner = Learner(LanguageProfile(native="en", target=Target("es-MX", Proficiency.A2)))
conversation = engine.start_session(learner).converse()


async def main() -> None:
    async for event in conversation.send_text("Hola, ¿cómo estás?"):
        if isinstance(event, TranscriptDelta):
            print(event.text, end="")


asyncio.run(main())
```

The engine does no I/O of its own: you pass it a configured provider (explicitly, as above, or
with `providers_from_env()` in `crowspeak_engine.llm` for scripts and tests) and it yields
events. Saving learners is also yours to do: `Learner.to_dict()` / `Learner.from_dict()` plus the
`LearnerStore` protocol. See [docs/engine-design.md](docs/engine-design.md).

### Developing the engine alongside a consumer

To use a local checkout of this repo from another project (for example the private backend) instead of
a published build, point `uv` at it. Edits to the engine show up immediately:

```toml
[project]
dependencies = ["crowspeak-engine"]

[tool.uv.sources]
crowspeak-engine = { path = "../crowspeak-core", editable = true }
```

Remove the `[tool.uv.sources]` entry to go back to the published package. The reference CLI in
this repo has the same switch: `make cli` uses the built package and `make cli-dev` the source.
Releasing is covered in [docs/releasing.md](docs/releasing.md).

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
