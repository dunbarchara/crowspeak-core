import asyncio
import json

import pytest

from crowspeak_engine import (
    AnalyzerError,
    CorrectionsReady,
    Corrections,
    Engine,
    EngineError,
    Features,
    InteractionPrefs,
    TurnCompleted,
)
from crowspeak_engine.analyzers import AnalysisError, AnalyzerContext
from crowspeak_engine.analyzers.corrections import MAX_ITEMS, build_prompt, parse_corrections
from crowspeak_engine.proficiency import Proficiency
from crowspeak_engine.proficiency_adapters import get_adapter

from conftest import GOOD_ANALYSIS, SPANISH_TEXT, FakeAnalyzerLLM, FakeLLM

ES_PREFS = InteractionPrefs(learner_input_language="es-MX", npc_response_language="es-MX")


def make(es_learner, npc_llm=None, analyzer=None, features=Features(corrections=True)):
    npc_llm = npc_llm or FakeLLM(chunks=("¡Hola!",))
    analyzer = analyzer or FakeAnalyzerLLM()
    engine = Engine(npc_llm, analyzer_llm=analyzer)
    session = engine.start_session(es_learner, ES_PREFS, features)
    return session.converse(), npc_llm, analyzer


async def collect(conv, text=SPANISH_TEXT):
    return [e async for e in conv.send_text(text)]


def ctx(text=SPANISH_TEXT, level=Proficiency.B2, history=()):
    return AnalyzerContext(
        text=text,
        history=history,
        target_language="es-MX",
        native_language="en",
        proficiency=level,
    )


# --- parsing -----------------------------------------------------------------------


def test_parse_computes_spans_orders_errors_first_and_sets_explanation_language():
    result = parse_corrections(json.dumps(GOOD_ANALYSIS), ctx())

    assert [i.original for i in result.items] == ["unos manzana", "yo fui"]  # error first
    for item in result.items:
        assert SPANISH_TEXT[item.span[0] : item.span[1]] == item.original
        assert item.explanation_language == "en"
    assert result.language == "es-MX"
    assert result.original == SPANISH_TEXT
    assert not result.is_correct
    assert result.praise == "¡Muy bien usaste el pretérito!"


def test_parse_repeated_quote_gets_distinct_spans_and_unfound_quote_has_no_span():
    text = "casa casa"
    item = {
        "original": "casa",
        "suggestion": "la casa",
        "category": "grammar",
        "severity": "error",
        "explanation": "x",
        "confidence": None,
    }
    missing = {**item, "original": "perro"}
    raw = json.dumps({"corrected": "x", "praise": None, "items": [item, item, missing]})

    spans = [i.span for i in parse_corrections(raw, ctx(text)).items]

    assert spans == [(0, 4), (5, 9), None]


def test_parse_caps_items_by_level_and_drops_noop_suggestions():
    def item(n, suggestion="otra"):
        return {
            "original": f"w{n}",
            "suggestion": suggestion if n else "w0",  # w0 is a no-op
            "category": "spelling",
            "severity": "error",
            "explanation": "x",
            "confidence": None,
        }

    raw = json.dumps({"corrected": "c", "praise": None, "items": [item(n) for n in range(8)]})
    text = " ".join(f"w{n}" for n in range(8))

    result = parse_corrections(raw, ctx(text, level=Proficiency.A1))

    assert len(result.items) == MAX_ITEMS[Proficiency.A1] == 2
    assert all(i.original != "w0" for i in result.items)


def test_parse_no_items_means_correct_and_blank_praise_is_none():
    raw = json.dumps({"corrected": "ignored", "praise": "  ", "items": []})

    result = parse_corrections(raw, ctx("Hola"))

    assert result.is_correct and result.items == ()
    assert result.corrected == "Hola" and result.praise is None


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        json.dumps({"corrected": "x", "praise": None}),  # no items
        json.dumps(
            {
                "corrected": "x",
                "praise": None,
                "items": [
                    {
                        "original": "a",
                        "suggestion": "b",
                        "category": "vibes",
                        "severity": "error",
                        "explanation": "x",
                    }
                ],
            }
        ),
    ],
)
def test_parse_rejects_unusable_output(raw):
    with pytest.raises(AnalysisError):
        parse_corrections(raw, ctx())


def test_corrections_round_trip_through_dict():
    result = parse_corrections(json.dumps(GOOD_ANALYSIS), ctx())
    assert Corrections.from_dict(json.loads(json.dumps(result.to_dict()))) == result


def test_prompt_has_no_persona_marks_history_and_names_the_message():
    history = (("NPC", "¿Qué compraste?"), ("LEARNER", "Nada"))
    system, user = build_prompt(ctx(history=history))

    assert "es-MX" in system["content"] and "B2" in system["content"]
    assert "[NPC] ¿Qué compraste?" in user["content"]
    assert "[LEARNER] Nada" in user["content"]
    assert user["content"].endswith(SPANISH_TEXT)


# --- turn flow ---------------------------------------------------------------------


async def test_corrections_follow_turn_completed_and_attach_to_the_message(es_learner):
    conv, npc_llm, analyzer = make(es_learner)

    events = await collect(conv)

    kinds = [type(e) for e in events]
    assert kinds.index(TurnCompleted) < kinds.index(CorrectionsReady) == len(kinds) - 1
    ready = events[-1]
    user_msg = conv.history[0]
    assert ready.message_id == user_msg.id
    assert ready.speaker_id == "user" and ready.conversation_id == conv.conversation_id
    assert user_msg.corrections == ready.corrections
    assert conv.history[1].corrections is None  # the NPC is never corrected
    assert len(analyzer.calls) == 1


async def test_npc_never_sees_corrections(es_learner):
    conv, npc_llm, _ = make(es_learner)
    await collect(conv)
    await collect(conv, "Hola otra vez")

    sent = json.dumps(npc_llm.calls[-1], ensure_ascii=False)
    assert "unas manzanas" not in sent and "explanation" not in sent


async def test_analyzer_gets_at_most_four_prior_messages_and_no_persona(es_learner):
    conv, _, analyzer = make(es_learner)
    for n in range(4):  # 8 messages of history
        await collect(conv, f"mensaje {n}")

    await collect(conv, "ultimo")

    user = analyzer.calls[-1][0][1]["content"]
    assert "mensaje 0" not in user and "mensaje 1" not in user
    assert "[LEARNER] mensaje 3" in user and "[NPC] ¡Hola!" in user
    assert user.endswith("ultimo")
    assert conv.npc.persona not in analyzer.calls[-1][0][0]["content"]


# --- gating ------------------------------------------------------------------------


async def test_off_by_default_makes_no_analyzer_call(es_learner):
    conv, _, analyzer = make(es_learner, features=None)

    events = await collect(conv)

    assert analyzer.calls == []
    assert not any(isinstance(e, (CorrectionsReady, AnalyzerError)) for e in events)
    assert conv.history[0].corrections is None


async def test_skipped_when_learner_writes_in_their_native_language(es_learner):
    engine = Engine(FakeLLM(), analyzer_llm=FakeAnalyzerLLM())
    prefs = InteractionPrefs(learner_input_language="en", npc_response_language="es-MX")
    conv = engine.start_session(es_learner, prefs, Features(corrections=True)).converse()

    events = await collect(conv, "I went to the market")

    assert not any(isinstance(e, CorrectionsReady) for e in events)


async def test_conversation_override_beats_session_default(es_learner):
    conv, _, analyzer = make(es_learner)
    conv.set_features(Features(corrections=False))

    await collect(conv)

    assert analyzer.calls == []


async def test_enabling_corrections_without_a_json_provider_fails_fast(es_learner):
    conv, _, _ = make(es_learner)
    conv._analyzer_llm = FakeLLM()  # no complete_json

    with pytest.raises(ValueError, match="complete_json"):
        await collect(conv)
    assert conv.history == []


async def test_analyzer_defaults_to_the_npc_provider(es_learner):
    class Both(FakeLLM, FakeAnalyzerLLM):
        def __init__(self):
            FakeLLM.__init__(self, chunks=("Hola",))
            FakeAnalyzerLLM.__init__(self)

    both = Both()
    conv = Engine(both).start_session(es_learner, ES_PREFS, Features(corrections=True)).converse()

    events = await collect(conv)

    assert isinstance(events[-1], CorrectionsReady)


# --- failure and cancellation ------------------------------------------------------


@pytest.mark.parametrize(
    "analyzer",
    [
        FakeAnalyzerLLM(error=RuntimeError("boom")),
        FakeAnalyzerLLM(result="not json"),
    ],
)
async def test_analyzer_failure_is_non_fatal(es_learner, analyzer):
    conv, _, _ = make(es_learner, analyzer=analyzer)

    events = await collect(conv)

    assert isinstance(events[-1], AnalyzerError) and events[-1].analyzer == "corrections"
    assert events[-1].message_id == conv.history[0].id
    assert not any(isinstance(e, EngineError) for e in events)
    assert [m.role for m in conv.history] == ["user", "assistant"]
    assert conv.history[0].corrections is None


async def test_consumer_leaving_before_corrections_still_attaches_them(es_learner):
    gate = asyncio.Event()
    conv, _, analyzer = make(es_learner, analyzer=FakeAnalyzerLLM(gate=gate))
    gen = conv.send_text(SPANISH_TEXT)
    async for event in gen:
        if isinstance(event, TurnCompleted):
            break
    await gen.aclose()

    gate.set()
    await asyncio.gather(*conv._analysis_tasks)

    assert conv.history[0].corrections is not None
    assert not analyzer.cancelled


async def test_cancelling_the_consumer_while_waiting_does_not_cancel_the_analysis(es_learner):
    gate = asyncio.Event()
    conv, _, analyzer = make(es_learner, analyzer=FakeAnalyzerLLM(gate=gate))

    consumer = asyncio.create_task(collect(conv))
    await asyncio.sleep(0.01)  # reply done; now awaiting the analysis
    consumer.cancel()
    await asyncio.gather(consumer, return_exceptions=True)
    gate.set()
    await asyncio.gather(*conv._analysis_tasks)

    assert conv.history[0].corrections is not None
    assert not analyzer.cancelled


async def test_npc_error_rolls_back_and_cancels_the_analysis(es_learner):
    class SlowFailingNpcLLM(FakeLLM):
        async def stream(self, messages):
            await asyncio.sleep(0)  # let the analysis start before the NPC reply fails
            raise RuntimeError("down")
            yield  # pragma: no cover

    gate = asyncio.Event()
    analyzer = FakeAnalyzerLLM(gate=gate)
    conv, _, _ = make(es_learner, npc_llm=SlowFailingNpcLLM(), analyzer=analyzer)

    events = await collect(conv)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert isinstance(events[-1], EngineError)
    assert conv.history == []
    assert analyzer.calls and analyzer.cancelled


# --- region codes ------------------------------------------------------------------


def test_region_code_falls_back_to_base_language_adapter():
    assert get_adapter("ja-JP", Proficiency.A1) == get_adapter("ja", Proficiency.A1)
    assert get_adapter("es-MX", Proficiency.A1) == get_adapter("xx", Proficiency.A1)  # generic
