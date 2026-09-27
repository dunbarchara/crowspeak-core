"""A conversation between the learner and one Npc."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, AsyncIterator

from .conversation_types import Message
from .events import ConversationEvent, EngineError, Event, TranscriptDelta, TurnCompleted
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
    ) -> None:
        self.conversation_id = str(uuid.uuid4())
        self.session = session
        self.npc = npc
        self.history: list[Message] = []
        self._llm = llm
        self._prefs = prefs
        self.resolve()  # fail fast on constraint violations

    @property
    def prefs(self) -> InteractionPrefs | None:
        return self._prefs

    def set_prefs(self, prefs: InteractionPrefs | None) -> None:
        resolve_prefs(self.session.learner.language, self.npc, prefs, self.session.prefs)
        self._prefs = prefs

    def resolve(self) -> tuple[str, str]:
        """The (input_language, response_language) currently in effect."""
        return resolve_prefs(
            self.session.learner.language, self.npc, self._prefs, self.session.prefs
        )

    def system_prompt(self) -> str:
        input_lang, response_lang = self.resolve()
        return build_system_prompt(
            self.session.learner.language, self.npc, input_lang, response_lang
        )

    def to_api_messages(self) -> list[dict]:
        messages = [{"role": "system", "content": self.system_prompt()}]
        messages.extend({"role": m.role, "content": m.content} for m in self.history)
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
        chunks: list[str] = []
        try:
            async for delta in self._llm.stream(self.to_api_messages()):
                chunks.append(delta)
                yield TranscriptDelta(text=delta, role="assistant", **ids)
        except Exception as e:
            self.history.pop()
            yield EngineError(message=str(e), recoverable=True, **ids)
            return

        message = Message(role="assistant", content="".join(chunks))
        self.history.append(message)
        yield TranscriptDelta(text="", role="assistant", final=True, **ids)
        yield TurnCompleted(message=message, **ids)
