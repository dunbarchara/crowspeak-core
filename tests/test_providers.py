import pytest
from conftest import FakeAnalyzerLLM, FakeLLM

from crowspeak_engine import (
    JOB_CORRECTIONS,
    JOB_NPC,
    CorrectionsReady,
    Engine,
    Features,
    InteractionPrefs,
    ProviderError,
    Providers,
    TurnCompleted,
)
from crowspeak_engine.analyzers import CorrectionsAnalyzer

ES_PREFS = InteractionPrefs(learner_input_language="es-MX", npc_response_language="es-MX")


class Both(FakeLLM, FakeAnalyzerLLM):
    """A provider with both stream() and complete_json()."""

    def __init__(self):
        FakeLLM.__init__(self)
        FakeAnalyzerLLM.__init__(self)


# --- the registry ------------------------------------------------------------------


def test_unset_job_falls_back_to_default():
    default = Both()

    providers = Providers(default=default)

    assert providers.for_job(JOB_NPC) is default
    assert providers.for_job("some-consumer-job", "json") is default


def test_assigned_job_gets_its_own_provider():
    default, own = Both(), Both()

    providers = Providers(default=default, jobs={"daily_tasks": own})

    assert providers.for_job("daily_tasks", "json") is own
    assert providers.for_job(JOB_NPC) is default


def test_missing_capability_names_the_job_and_the_method():
    providers = Providers(default=FakeLLM(), jobs={JOB_CORRECTIONS: FakeLLM()})

    with pytest.raises(ProviderError, match="corrections.*complete_json") as e:
        providers.for_job(JOB_CORRECTIONS, "json")
    assert "assigned to it" in str(e.value)

    with pytest.raises(ProviderError, match="'npc'.*stream.*the default"):
        Providers(default=FakeAnalyzerLLM()).for_job(JOB_NPC)


def test_provider_error_is_a_value_error():
    assert issubclass(ProviderError, ValueError)


def test_jobs_are_copied_and_read_only():
    jobs = {"a": FakeLLM()}
    providers = Providers(default=FakeLLM(), jobs=jobs)

    jobs["b"] = FakeLLM()

    assert set(providers.jobs) == {"a"}
    with pytest.raises(TypeError):
        providers.jobs["c"] = FakeLLM()  # type: ignore[index]


def test_analyzer_name_is_its_job_name():
    assert CorrectionsAnalyzer.name == JOB_CORRECTIONS


# --- engine wiring -----------------------------------------------------------------


def test_shorthand_matches_explicit_registry():
    npc, analyzer = FakeLLM(), FakeAnalyzerLLM()

    providers = Engine(npc, analyzer_llm=analyzer).providers

    assert providers.default is npc
    assert providers.for_job(JOB_CORRECTIONS, "json") is analyzer
    assert dict(providers.jobs) == {JOB_CORRECTIONS: analyzer}


def test_shorthand_without_analyzer_assigns_no_jobs():
    assert dict(Engine(FakeLLM()).providers.jobs) == {}


def test_engine_rejects_both_forms_and_neither():
    with pytest.raises(ValueError, match="not both"):
        Engine(FakeLLM(), providers=Providers(default=FakeLLM()))
    with pytest.raises(ValueError, match="not both"):
        Engine(analyzer_llm=FakeAnalyzerLLM(), providers=Providers(default=FakeLLM()))
    with pytest.raises(ValueError, match="providers= or an llm"):
        Engine()


async def test_npc_job_provider_streams_the_reply(learner):
    default, npc = FakeLLM(chunks=("default",)), FakeLLM(chunks=("npc",))
    engine = Engine(providers=Providers(default=default, jobs={JOB_NPC: npc}))
    conv = engine.start_session(learner).converse()

    events = [e async for e in conv.send_text("hi")]

    assert [e for e in events if isinstance(e, TurnCompleted)][0].message.content == "npc"
    assert npc.calls and default.calls == []


async def test_default_serves_corrections_when_only_npc_is_overridden(es_learner):
    default = Both()
    npc = FakeLLM(chunks=("¡Hola!",))
    engine = Engine(providers=Providers(default=default, jobs={JOB_NPC: npc}))
    conv = engine.start_session(es_learner, ES_PREFS, Features(corrections=True)).converse()

    events = await _drain(conv)

    assert isinstance(events[-1], CorrectionsReady)
    assert len(npc.calls) == 1  # the reply
    assert len(default.calls) == 1  # Both's shared `calls` list: only the complete_json call


async def test_converse_fails_fast_when_the_npc_provider_cannot_stream(learner):
    engine = Engine(providers=Providers(default=FakeAnalyzerLLM()))
    session = engine.start_session(learner)

    with pytest.raises(ProviderError, match="stream"):
        session.converse()


async def _drain(conv):
    return [e async for e in conv.send_text("Ayer yo fui al mercado y compré unos manzana.")]
