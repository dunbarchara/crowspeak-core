from conftest import FakeLLM

from crowspeak_engine import Engine, EngineError, TranscriptDelta, TurnCompleted


async def collect(conv, text):
    return [e async for e in conv.send_text(text)]


async def test_normal_turn_event_sequence(session, llm):
    conv = session.converse()
    events = await collect(conv, "こんにちは")
    kinds = [type(e) for e in events]
    assert kinds == [TranscriptDelta, TranscriptDelta, TranscriptDelta, TurnCompleted]
    assert [e.text for e in events[:2]] == ["Hel", "lo"]
    assert events[2].final
    assert events[-1].message.content == "Hello"
    assert all(e.conversation_id == conv.conversation_id for e in events)
    assert all(e.speaker_id == conv.npc.id for e in events)
    assert [m.role for m in conv.history] == ["user", "assistant"]
    assert llm.calls[0][0]["role"] == "system"
    assert llm.calls[0][-1] == {"role": "user", "content": "こんにちは"}


async def test_provider_failure_rolls_back_and_conversation_stays_usable(learner):
    llm = FakeLLM(chunks=[], error=RuntimeError("boom"))
    conv = Engine(llm).start_session(learner).converse()
    events = await collect(conv, "hi")
    assert len(events) == 1 and isinstance(events[0], EngineError)
    assert events[0].message == "boom" and conv.history == []

    llm.error = None
    llm.chunks = ["ok"]
    events = await collect(conv, "again")
    assert isinstance(events[-1], TurnCompleted)
    assert len(conv.history) == 2


def test_start_event(session):
    ev = session.start_event()
    assert ev.session_id == session.session_id and ev.learner_id == session.learner.id
