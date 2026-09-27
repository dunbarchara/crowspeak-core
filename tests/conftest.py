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
