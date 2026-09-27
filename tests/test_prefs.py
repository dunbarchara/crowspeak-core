import pytest

from crowspeak_engine import (
    ConstraintError,
    InteractionPrefs,
    LanguageProfile,
    Npc,
    Proficiency,
)
from crowspeak_engine.prefs import resolve_prefs

JA_NPC = Npc(id="ja", name="Yuki", persona="p", language=LanguageProfile(native="ja"))


def test_natural_default_is_native_in_target_out(learner):
    assert resolve_prefs(learner.language, JA_NPC) == ("en", "ja")


@pytest.mark.parametrize("i", ["en", "ja", "fr"])
@pytest.mark.parametrize("r", ["en", "ja", "fr"])
def test_any_combination_is_accepted_by_default(learner, i, r):
    assert resolve_prefs(learner.language, JA_NPC, InteractionPrefs(i, r)) == (i, r)


def test_conversation_overrides_session(learner):
    conv = InteractionPrefs("ja", None)
    sess = InteractionPrefs("en", "en")
    assert resolve_prefs(learner.language, JA_NPC, conv, sess) == ("ja", "en")


def test_constrained_npc_natural_default_adapts(learner):
    npc = Npc(
        id="x", name="X", persona="p", language=LanguageProfile(native="ja"),
        understands=frozenset({"ja"}), speaks=frozenset({"ja"}),
    )
    assert resolve_prefs(learner.language, npc) == ("ja", "ja")


def test_explicit_prefs_violating_constraints_raise(learner):
    npc = Npc(
        id="x", name="X", persona="p", language=LanguageProfile(native="ja"),
        understands=frozenset({"ja"}),
    )
    with pytest.raises(ConstraintError):
        resolve_prefs(learner.language, npc, InteractionPrefs("en", None))


def test_non_native_beginner_npc_speaks_learners_target(learner):
    npc = Npc(
        id="b", name="Bo", persona="p",
        language=LanguageProfile(native="en", target="ja", proficiency=Proficiency.A1),
    )
    assert resolve_prefs(learner.language, npc) == ("en", "ja")
