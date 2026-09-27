"""Live Azure Foundry smoke test. Costs real money; opt-in only: `pytest -m live`."""

import pytest

from crowspeak_engine.llm.azure_openai import AzureOpenAIProvider

pytestmark = pytest.mark.live


async def test_azure_streams_text():
    provider = AzureOpenAIProvider.from_env()

    text = "".join(
        [d async for d in provider.stream([{"role": "user", "content": "Say hi in one word."}])]
    )

    assert text.strip()
