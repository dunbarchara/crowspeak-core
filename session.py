"""Session state for a single language-practice conversation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

from proficiency import Proficiency
from proficiency_adapters import get_adapter

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass
class Session:
    session_id: str
    native_language: str
    target_language: str
    proficiency: Proficiency
    user_input_language: str
    llm_response_language: str
    history: list[Message] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.native_language == self.target_language:
            raise ValueError("native_language and target_language must differ")

        valid_languages = {self.native_language, self.target_language}
        if self.user_input_language not in valid_languages:
            raise ValueError(
                f"user_input_language must be one of {valid_languages}, "
                f"got {self.user_input_language!r}"
            )
        if self.llm_response_language not in valid_languages:
            raise ValueError(
                f"llm_response_language must be one of {valid_languages}, "
                f"got {self.llm_response_language!r}"
            )

    def build_system_prompt(self) -> str:
        adapter = get_adapter(self.target_language, self.proficiency)
        return (
            "You are a conversational language-practice partner. The user is "
            f"a native {self.native_language} speaker practicing "
            f"{self.target_language} at CEFR level {self.proficiency.value}.\n"
            f"The user will write to you in {self.user_input_language}; "
            f"you must respond only in {self.llm_response_language}.\n"
            f"{adapter}"
        )

    def add_user_message(self, content: str) -> None:
        self.history.append(Message(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        self.history.append(Message(role="assistant", content=content))

    def to_api_messages(self) -> list[dict]:
        """Flatten the system prompt and history into OpenAI-style messages."""
        messages = [{"role": "system", "content": self.build_system_prompt()}]
        messages.extend({"role": m.role, "content": m.content} for m in self.history)
        return messages

    @classmethod
    def begin(
        cls,
        *,
        native_language: str,
        target_language: str,
        proficiency: Proficiency,
        user_input_language: str,
        llm_response_language: str,
    ) -> Session:
        return cls(
            session_id=str(uuid.uuid4()),
            native_language=native_language,
            target_language=target_language,
            proficiency=proficiency,
            user_input_language=user_input_language,
            llm_response_language=llm_response_language,
        )
