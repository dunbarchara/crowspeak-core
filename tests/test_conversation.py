import asyncio

import pytest
from conftest import FakeLLM

from crowspeak_engine import (
    Engine,
    EngineError,
    ExpressionChange,
    Features,
    LanguageProfile,
    Npc,
    TranscriptDelta,
    TurnCompleted,
)


ON = Features(expression=True)


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


async def test_deltas_join_trivially_into_full_message(session, llm):
    """A non-streaming consumer should be able to reconstruct the full reply by
    joining every non-final TranscriptDelta's text, in order."""
    conv = session.converse()
    events = await collect(conv, "hi")
    deltas = [e for e in events if isinstance(e, TranscriptDelta) and not e.final]
    joined = "".join(e.text for e in deltas)
    turn_completed = events[-1]
    assert isinstance(turn_completed, TurnCompleted)
    assert joined == turn_completed.message.content == "Hello"


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


async def test_cancellation_mid_stream_persists_partial_reply_as_interrupted(session, llm):
    llm.chunks = ["Hel", "lo", " world"]
    conv = session.converse()
    gen = conv.send_text("hi")
    await gen.__anext__()  # "Hel"
    await gen.__anext__()  # "lo"
    await gen.aclose()  # consumer disconnects before " world" / TurnCompleted

    assert [m.role for m in conv.history] == ["user", "assistant"]
    reply = conv.history[-1]
    assert reply.content == "Hello"
    assert reply.interrupted is True


async def test_cancellation_before_any_output_rolls_back(learner):
    hung = asyncio.Event()

    class HangingLLM:
        calls: list[list[dict]] = []

        async def stream(self, messages):
            self.calls.append(messages)
            await hung.wait()
            yield "unreachable"  # pragma: no cover

    conv = Engine(HangingLLM()).start_session(learner).converse()
    task = asyncio.ensure_future(collect(conv, "hi"))
    await asyncio.sleep(0)  # let send_text append the user message and start streaming
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert conv.history == []


async def test_multi_npc_events_are_isolated_per_conversation(session, llm):
    alice = Npc(id="alice", name="Alice", persona="", language=LanguageProfile(native="ja"))
    bob = Npc(id="bob", name="Bob", persona="", language=LanguageProfile(native="ja"))

    conv_a = session.converse(alice)
    events_a = await collect(conv_a, "hi alice")
    assert all(e.conversation_id == conv_a.conversation_id for e in events_a)
    assert all(e.speaker_id == "alice" for e in events_a)

    llm.chunks = ["Hel", "lo"]
    conv_b = session.converse(bob)
    events_b = await collect(conv_b, "hi bob")
    assert all(e.conversation_id == conv_b.conversation_id for e in events_b)
    assert all(e.speaker_id == "bob" for e in events_b)

    assert conv_a.conversation_id != conv_b.conversation_id
    assert len(conv_a.history) == 2
    assert len(conv_b.history) == 2


async def test_tags_become_expression_events_and_are_stripped_from_text(session, llm):
    llm.chunks = ["[hap", "py] Bonjour", "! [thinking] ", "Et toi ?"]
    conv = session.converse(features=ON)
    events = await collect(conv, "hi")

    kinds = [type(e) for e in events]
    assert kinds[0] is ExpressionChange and events[0].label == "happy"
    assert kinds[-1] is TurnCompleted
    labels = [e.label for e in events if isinstance(e, ExpressionChange)]
    assert labels == ["happy", "thinking"]
    text = "".join(e.text for e in events if isinstance(e, TranscriptDelta))
    assert text == "Bonjour! Et toi ?"
    # the expression precedes the first non-empty text
    first_text = next(i for i, e in enumerate(events) if isinstance(e, TranscriptDelta))
    assert first_text > 0 and isinstance(events[first_text - 1], ExpressionChange)

    message = events[-1].message
    assert message.content == "Bonjour! Et toi ?"
    assert message.raw == "[happy] Bonjour! [thinking] Et toi ?"


async def test_history_sent_back_to_llm_keeps_tags(session, llm):
    llm.chunks = ["[sad] Oh no."]
    conv = session.converse(features=ON)
    await collect(conv, "first")
    await collect(conv, "second")
    assistant = [m for m in llm.calls[1] if m["role"] == "assistant"]
    assert assistant == [{"role": "assistant", "content": "[sad] Oh no."}]
    assert conv.history[1].content == "Oh no."


async def test_reply_with_only_a_tag_still_completes(session, llm):
    llm.chunks = ["[angry]"]
    events = await collect(session.converse(features=ON), "hi")
    assert [e.label for e in events if isinstance(e, ExpressionChange)] == ["angry"]
    assert events[-1].message.content == ""


async def test_cancellation_persists_clean_text_and_raw(session, llm):
    llm.chunks = ["[happy] Hel", "lo", " world"]
    conv = session.converse(features=ON)
    gen = conv.send_text("hi")
    await gen.__anext__()  # ExpressionChange(happy)
    await gen.__anext__()  # "Hel"
    await gen.aclose()

    reply = conv.history[-1]
    assert reply.interrupted is True
    assert reply.content == "Hel"
    assert reply.raw == "[happy] Hel"


async def test_expression_on_defaults_to_neutral_before_first_text(session, llm):
    events = await collect(session.converse(features=ON), "hi")
    assert [type(e) for e in events] == [
        ExpressionChange,
        TranscriptDelta,
        TranscriptDelta,
        TranscriptDelta,
        TurnCompleted,
    ]
    assert events[0].label == "neutral"


async def test_expression_off_by_default_strips_stray_tags_without_events(session, llm):
    llm.chunks = ["[happy] Bon", "jour"]
    conv = session.converse()
    events = await collect(conv, "hi")
    assert not any(isinstance(e, ExpressionChange) for e in events)
    assert "".join(e.text for e in events if isinstance(e, TranscriptDelta)) == "Bonjour"
    assert events[-1].message.content == "Bonjour"
    assert "[happy]" not in llm.calls[0][0]["content"]  # no tag instruction in the prompt


async def test_session_default_and_conversation_override(session, llm):
    session.set_features(ON)
    on_conv = session.converse()
    off = Npc(id="off", name="Off", persona="", language=LanguageProfile(native="ja"))
    off_conv = session.converse(off, features=Features(expression=False))

    assert any(isinstance(e, ExpressionChange) for e in await collect(on_conv, "hi"))
    assert not any(isinstance(e, ExpressionChange) for e in await collect(off_conv, "hi"))


async def test_toggling_expression_between_turns(session, llm):
    llm.chunks = ["[sad] Oh no."]
    conv = session.converse(features=ON)
    await collect(conv, "one")
    conv.set_features(Features(expression=False))
    events = await collect(conv, "two")

    # off: no events, clean prompt, and the earlier tagged reply is sent back untagged
    assert not any(isinstance(e, ExpressionChange) for e in events)
    assert "[sad]" not in llm.calls[1][0]["content"]
    assert {"role": "assistant", "content": "Oh no."} in llm.calls[1]

    conv.set_features(ON)
    await collect(conv, "three")
    assert "[sad]" in llm.calls[2][0]["content"]
    assert {"role": "assistant", "content": "[sad] Oh no."} in llm.calls[2]
