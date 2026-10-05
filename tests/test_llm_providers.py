from types import SimpleNamespace

import pytest

from crowspeak_engine.llm import provider_from_env
from crowspeak_engine.llm._openai_stream import stream_deltas
from crowspeak_engine.llm.azure_openai import AzureOpenAIProvider
from crowspeak_engine.llm.local import DEFAULT_BASE_URL, DEFAULT_MODEL, LocalOpenAIProvider


def _chunk(content=None, *, choices=True):
    if not choices:
        return SimpleNamespace(choices=[])
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content))])


class FakeClient:
    def __init__(self, chunks):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._chunks = chunks

    async def _create(self, **kwargs):
        self.calls.append(kwargs)

        async def gen():
            for c in self._chunks:
                yield c

        return gen()


async def test_stream_deltas_skips_empty_and_choiceless_chunks():
    client = FakeClient([_chunk("Hel"), _chunk(choices=False), _chunk(None), _chunk("lo")])
    messages = [{"role": "user", "content": "hi"}]

    out = [d async for d in stream_deltas(client, "m", messages)]

    assert out == ["Hel", "lo"]
    assert client.calls == [{"model": "m", "messages": messages, "stream": True}]


def test_factory_defaults_to_azure(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "d")

    assert isinstance(provider_from_env(), AzureOpenAIProvider)


def test_factory_selects_local(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "Local")
    monkeypatch.delenv("LOCAL_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LOCAL_LLM_MODEL", raising=False)

    provider = provider_from_env()

    assert isinstance(provider, LocalOpenAIProvider)
    assert provider._model == DEFAULT_MODEL
    assert str(provider._client.base_url).rstrip("/") == DEFAULT_BASE_URL


def test_local_from_env_overrides(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://host:1234/v1")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen2.5")

    provider = LocalOpenAIProvider.from_env()

    assert provider._model == "qwen2.5"
    assert str(provider._client.base_url).rstrip("/") == "http://host:1234/v1"


def test_factory_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bogus")

    with pytest.raises(ValueError, match="azure, local"):
        provider_from_env()


async def test_complete_json_sends_strict_schema_and_returns_text():
    from crowspeak_engine.llm._openai_stream import complete_json

    reply = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"a": 1}'))])
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        return reply

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    schema = {"type": "object"}

    out = await complete_json(client, "m", [{"role": "user", "content": "hi"}], schema)

    assert out == '{"a": 1}'
    assert "stream" not in calls[0]
    assert calls[0]["response_format"]["json_schema"] == {
        "name": "analysis",
        "schema": schema,
        "strict": True,
    }


def test_both_adapters_expose_complete_json():
    from crowspeak_engine.llm.base import JSONProvider  # noqa: F401

    assert hasattr(LocalOpenAIProvider(), "complete_json")
    assert hasattr(
        AzureOpenAIProvider(endpoint="https://x.openai.azure.com/", api_key="k", deployment="d"),
        "complete_json",
    )
