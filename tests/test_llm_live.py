"""Live Azure Foundry smoke test. Costs real money; opt-in only: `pytest -m live`."""

import pytest

from crowspeak_engine.llm import provider_from_env

pytestmark = pytest.mark.live


async def test_azure_streams_text(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    provider = provider_from_env()

    text = "".join(
        [d async for d in provider.stream([{"role": "user", "content": "Say hi in one word."}])]
    )

    assert text.strip()
