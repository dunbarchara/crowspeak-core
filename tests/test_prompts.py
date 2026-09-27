from crowspeak_engine import InteractionPrefs, LanguageProfile, Npc, Proficiency
from crowspeak_engine.proficiency_adapters import get_adapter


def test_native_npc_calibrates_to_learner(session):
    prompt = session.converse().system_prompt()
    assert get_adapter("ja", Proficiency.A2) in prompt
    assert "respond only in ja" in prompt


def test_beginner_non_native_npc_calibrates_to_npc(session):
    npc = Npc(
        id="b", name="Bo", persona="I am Bo.",
        language=LanguageProfile(native="en", target="ja", proficiency=Proficiency.A1),
    )
    prompt = session.converse(npc).system_prompt()
    assert prompt.startswith("I am Bo.")
    assert get_adapter("ja", Proficiency.A1) in prompt
    assert get_adapter("ja", Proficiency.A2) not in prompt


def test_no_calibration_when_replying_in_learner_native(session):
    conv = session.converse(prefs=InteractionPrefs("ja", "en"))
    prompt = conv.system_prompt()
    assert "respond only in en" in prompt
    assert get_adapter("ja", Proficiency.A2) not in prompt


def test_constraints_appear_in_prompt(session):
    npc = Npc(
        id="s", name="S", persona="p", language=LanguageProfile(native="ja"),
        understands=frozenset({"ja"}), speaks=frozenset({"ja"}),
    )
    prompt = session.converse(npc).system_prompt()
    assert "only understand ja" in prompt and "only speak ja" in prompt
