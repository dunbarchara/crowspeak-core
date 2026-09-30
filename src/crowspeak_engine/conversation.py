"""A conversation between the learner and one Npc."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, AsyncIterator

from .conversation_types import Message
from .events import (
    ConversationEvent,
    EngineError,
    Event,
    ExpressionChange,
    TranscriptDelta,
    TurnCompleted,
)
from .expression import DEFAULT_EXPRESSION, EXPRESSIONS, Expression, ExpressionTagParser
from .features import Features, ResolvedFeatures, resolve_features
from .llm.base import LLMProvider
from .npc import Npc
from .prefs import InteractionPrefs, resolve_prefs
from .prompts import build_system_prompt

if TYPE_CHECKING:
    from .session import Session


class Conversation:
    """Owns the per-Npc history and turn loop. Learner config and default prefs
    come from the (world-level) Session it belongs to."""

    def __init__(
        self,
        session: Session,
        npc: Npc,
        llm: LLMProvider,
        prefs: InteractionPrefs | None = None,
        features: Features | None = None,
    ) -> None:
        self.conversation_id = str(uuid.uuid4())
        self.session = session
        self.npc = npc
        self.history: list[Message] = []
        self._llm = llm
        self._prefs = prefs
        self._features = features
        self.resolve()  # fail fast on constraint violations

    @property
    def prefs(self) -> InteractionPrefs | None:
        return self._prefs

    def set_prefs(self, prefs: InteractionPrefs | None) -> None:
        resolve_prefs(self.session.learner.language, self.npc, prefs, self.session.prefs)
        self._prefs = prefs

    @property
    def features(self) -> Features | None:
        return self._features

    def set_features(self, features: Features | None) -> None:
        """Override the session's feature defaults for this conversation; applies next turn."""
        self._features = features

    def resolved_features(self) -> ResolvedFeatures:
        return resolve_features(self._features, self.session.features)

    def resolve(self) -> tuple[str, str]:
        """The (input_language, response_language) currently in effect."""
        return resolve_prefs(
            self.session.learner.language, self.npc, self._prefs, self.session.prefs
        )

    def system_prompt(self) -> str:
        input_lang, response_lang = self.resolve()
        return build_system_prompt(
            self.session.learner.language,
            self.npc,
            input_lang,
            response_lang,
            expressions=EXPRESSIONS if self.resolved_features().expression else (),
        )

    def to_api_messages(self) -> list[dict]:
        messages = [{"role": "system", "content": self.system_prompt()}]
        # With expression on, send the model its own tagged output so it keeps following
        # the tag format; otherwise send clean text so it never sees tags.
        tagged = self.resolved_features().expression
        messages.extend(
            {"role": m.role, "content": (m.raw or m.content) if tagged else m.content}
            for m in self.history
        )
        return messages

    def _ids(self, speaker_id: str) -> dict:
        return {
            "session_id": self.session.session_id,
            "conversation_id": self.conversation_id,
            "speaker_id": speaker_id,
        }

    async def send_text(self, text: str) -> AsyncIterator[Event]:
        """Send a learner message and stream the Npc's reply as events."""
        self.history.append(Message(role="user", content=text))
        ids = self._ids(self.npc.id)
        chunks: list[str] = []  # clean text, tags stripped
        raw_chunks: list[str] = []  # as the model produced it
        # Read once per turn. The parser always runs so stray tags never reach the
        # client, but events are only emitted when the feature is on.
        emit_expression = self.resolved_features().expression
        parser = ExpressionTagParser()
        expressed = False  # with expression on, every turn gets one before its first text

        def render(items: list[str | Expression]) -> list[Event]:
            nonlocal expressed
            events: list[Event] = []
            for item in items:
                if isinstance(item, Expression):
                    if emit_expression:
                        expressed = True
                        events.append(ExpressionChange(label=item.label, **ids))
                    continue
                if emit_expression and not expressed:
                    expressed = True
                    events.append(ExpressionChange(label=DEFAULT_EXPRESSION, **ids))
                chunks.append(item)
                events.append(TranscriptDelta(text=item, role="assistant", **ids))
            return events

        # True once the stream has settled one way or another (finished normally, or a
        # provider error was already handled below) — i.e. no cancellation cleanup needed.
        settled = False
        try:
            try:
                async for delta in self._llm.stream(self.to_api_messages()):
                    raw_chunks.append(delta)
                    for event in render(parser.feed(delta)):
                        yield event
                for event in render(parser.finish()):
                    yield event
                settled = True
            except Exception as e:
                self.history.pop()
                yield EngineError(message=str(e), recoverable=True, **ids)
                settled = True
                return
        finally:
            # Reached on cancellation (GeneratorExit / asyncio.CancelledError) mid-stream,
            # i.e. `settled` is still False because neither branch above ran to completion.
            # Can't yield an event here (the consumer, by definition, has stopped listening)
            # — just keep history coherent so a later reader can resume the conversation.
            if not settled:
                if chunks:
                    self.history.append(
                        Message(
                            role="assistant",
                            content="".join(chunks),
                            interrupted=True,
                            raw="".join(raw_chunks),
                        )
                    )
                else:
                    self.history.pop()

        if emit_expression and not expressed:  # reply with no text at all
            yield ExpressionChange(label=DEFAULT_EXPRESSION, **ids)
        message = Message(role="assistant", content="".join(chunks), raw="".join(raw_chunks))
        self.history.append(message)
        yield TranscriptDelta(text="", role="assistant", final=True, **ids)
        yield TurnCompleted(message=message, **ids)
