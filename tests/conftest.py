import asyncio
import json

import pytest

from crowspeak_engine import Engine, LanguageProfile, Learner, Proficiency


class FakeLLM:
    def __init__(self, chunks=("Hel", "lo"), error=None):
        self.chunks = list(chunks)
        self.error = error
        self.calls: list[list[dict]] = []

    async def stream(self, messages):
        self.calls.append(messages)
        for c in self.chunks:
            yield c
        if self.error:
            raise self.error


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def learner():
    return Learner(LanguageProfile(native="en", target="ja", proficiency=Proficiency.A2))


@pytest.fixture
def session(llm, learner):
    return Engine(llm).start_session(learner)


class FakeAnalyzerLLM:
    """Stands in for a JSON-capable analyzer provider. `result` is a dict (dumped to JSON)
    or a raw string; `gate` (an asyncio.Event) holds the call open until set."""

    def __init__(self, result=None, error=None, gate=None):
        self.result = GOOD_ANALYSIS if result is None else result
        self.error = error
        self.gate = gate
        self.calls: list[tuple[list[dict], dict]] = []
        self.cancelled = False

    async def complete_json(self, messages, schema):
        self.calls.append((messages, schema))
        try:
            if self.gate is not None:
                await self.gate.wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        if self.error:
            raise self.error
        return self.result if isinstance(self.result, str) else json.dumps(self.result)


GOOD_ANALYSIS = {
    "corrected": "Ayer fui al mercado y compré unas manzanas.",
    "praise": "¡Muy bien usaste el pretérito!",
    "items": [
        {
            "original": "yo fui",
            "suggestion": "fui",
            "category": "naturalness",
            "severity": "suggestion",
            "explanation": "Spanish usually drops the subject pronoun.",
            "confidence": 0.7,
        },
        {
            "original": "unos manzana",
            "suggestion": "unas manzanas",
            "category": "grammar",
            "severity": "error",
            "explanation": "'Manzana' is feminine and plural here.",
            "confidence": None,
        },
    ],
}

SPANISH_TEXT = "Ayer yo fui al mercado y compré unos manzana."


@pytest.fixture
def es_learner():
    return Learner(LanguageProfile(native="en", target="es-MX", proficiency=Proficiency.A2))
