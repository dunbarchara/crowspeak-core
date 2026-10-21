import json

import pytest
from conftest import FakeAnalyzerLLM, FakeLLM

from crowspeak_engine import (
    Engine,
    GenerationError,
    GeneratorContext,
    ProviderError,
    Providers,
)
from crowspeak_engine.generators import validate

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tasks"],
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "level"],
                "properties": {
                    "title": {"type": "string"},
                    "level": {"type": "string", "enum": ["easy", "hard"]},
                    "hint": {"type": ["string", "null"]},
                },
            },
        }
    },
}
GOOD = {"tasks": [{"title": "Order tacos", "level": "easy", "hint": None}]}


class DailyTasks:
    name = "daily_tasks"
    job = "daily_tasks"
    schema = SCHEMA

    def build_prompt(self, ctx: GeneratorContext) -> list[dict]:
        count = ctx.params.get("count", 3)
        return [
            {
                "role": "user",
                "content": f"{count} tasks in {ctx.target_language} at {ctx.proficiency.value}",
            }
        ]

    def parse(self, data, ctx):
        return [t["title"] for t in data["tasks"]]


class BadParse(DailyTasks):
    def parse(self, data, ctx):
        raise ValueError("nope")


async def test_default_provider_serves_a_consumer_generator(es_learner):
    llm = FakeAnalyzerLLM(GOOD)
    out = await Engine(providers=Providers(default=llm)).generate(DailyTasks(), es_learner)
    assert out == ["Order tacos"]


async def test_prompt_receives_learner_and_params(es_learner):
    llm = FakeAnalyzerLLM(GOOD)
    await Engine(providers=Providers(default=llm)).generate(DailyTasks(), es_learner, count=5)
    messages, schema = llm.calls[0]
    assert "5 tasks in es-MX at A2" in messages[0]["content"]
    assert schema is SCHEMA


async def test_job_provider_wins_over_default(es_learner):
    own, default = FakeAnalyzerLLM(GOOD), FakeAnalyzerLLM(GOOD)
    engine = Engine(providers=Providers(default=default, jobs={"daily_tasks": own}))
    await engine.generate(DailyTasks(), es_learner)
    assert len(own.calls) == 1 and not default.calls


async def test_provider_without_json_raises_provider_error(es_learner):
    with pytest.raises(ProviderError, match="daily_tasks"):
        await Engine(FakeLLM()).generate(DailyTasks(), es_learner)


async def test_provider_failure_is_wrapped(es_learner):
    llm = FakeAnalyzerLLM(error=RuntimeError("boom"))
    with pytest.raises(GenerationError, match="boom"):
        await Engine(llm).generate(DailyTasks(), es_learner)


async def test_parse_failure_is_wrapped(es_learner):
    with pytest.raises(GenerationError, match="daily_tasks"):
        await Engine(FakeAnalyzerLLM(GOOD)).generate(BadParse(), es_learner)


@pytest.mark.parametrize(
    "reply, message",
    [
        ("not json", "not valid JSON"),
        ({"tasks": "x"}, r"\$\.tasks: expected array"),
        ({}, "missing required field 'tasks'"),
        ({"tasks": [], "extra": 1}, "unexpected field 'extra'"),
        ({"tasks": [{"title": "a", "level": "mid"}]}, r"\$\.tasks\[0\]\.level"),
        ({"tasks": [{"title": 3, "level": "easy"}]}, r"\$\.tasks\[0\]\.title"),
    ],
)
async def test_invalid_output_raises_generation_error(es_learner, reply, message):
    with pytest.raises(GenerationError, match=message):
        await Engine(FakeAnalyzerLLM(reply)).generate(DailyTasks(), es_learner)


def test_validate_accepts_nullable_and_rejects_bool_as_number():
    assert validate(json.dumps(GOOD), SCHEMA) == GOOD
    with pytest.raises(GenerationError):
        validate("true", {"type": "number"})
    assert validate("1.5", {"type": ["number", "null"]}) == 1.5


def test_context_params_are_read_only(es_learner):
    ctx = GeneratorContext(es_learner, {"a": 1})
    with pytest.raises(TypeError):
        ctx.params["a"] = 2  # type: ignore[index]
