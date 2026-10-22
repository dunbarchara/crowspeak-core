"""The CLI's per-job provider reporting. Pure functions: no env reads beyond the one
monkeypatched case, no network."""

import sys

import pytest
from conftest import FakeLLM

from crowspeak_cli.cli import _debug_env, _load_env, _provider_lines
from crowspeak_engine import Providers


class Described(FakeLLM):
    def __init__(self, label):
        super().__init__()
        self.label = label

    def describe(self):
        return self.label


def test_jobs_without_their_own_provider_show_the_default():
    providers = Providers(default=Described("local model=a"))

    assert _provider_lines(providers, corrections=True) == [
        "default: local model=a",
        "npc: (default)",
        "corrections: (default)",
    ]


def test_assigned_job_shows_its_own_provider():
    providers = Providers(
        default=Described("local model=a"),
        jobs={"corrections": Described("azure deployment=big")},
    )

    lines = _provider_lines(providers, corrections=True)

    assert lines[1] == "npc: (default)"
    assert lines[2] == "corrections: azure deployment=big"


def test_corrections_job_is_marked_unused_when_the_feature_is_off():
    providers = Providers(
        default=Described("local model=a"),
        jobs={"corrections": Described("azure deployment=big")},
    )

    lines = _provider_lines(providers, corrections=False)

    assert lines[2] == "corrections: azure deployment=big (unused: --corrections is off)"


def test_provider_without_describe_falls_back_to_repr():
    llm = FakeLLM()

    assert _provider_lines(Providers(default=llm), corrections=True)[0] == f"default: {llm!r}"


def test_debug_env_lists_only_provider_selecting_variables(monkeypatch):
    for name in ("LLM_PROVIDER", "LLM_NPC_MODEL", "LLM_CORRECTIONS_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    assert _debug_env() == "(none set; defaults apply)"

    monkeypatch.setenv("LLM_PROVIDER", "local")
    monkeypatch.setenv("LLM_CORRECTIONS_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "must-not-appear")
    monkeypatch.setenv("LLM_CORRECTIONS_API_KEY", "also-must-not-appear")

    out = _debug_env()

    assert out == (
        "LLM_CORRECTIONS_API_KEY=(set) LLM_CORRECTIONS_PROVIDER=azure LLM_PROVIDER=local"
    )
    assert "must-not-appear" not in out


def test_missing_dotenv_exits_with_the_install_command(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "dotenv", None)  # makes `import dotenv` raise ImportError

    with pytest.raises(SystemExit) as e:
        _load_env()

    assert e.value.code == 1
    assert "uv sync --group cli" in capsys.readouterr().err
