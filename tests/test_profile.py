import pytest

from crowspeak_engine import LanguageProfile, Learner, Proficiency


def test_target_requires_proficiency():
    with pytest.raises(ValueError):
        LanguageProfile(native="en", target="ja")
    with pytest.raises(ValueError):
        LanguageProfile(native="en", proficiency=Proficiency.A1)


def test_native_and_target_must_differ():
    with pytest.raises(ValueError):
        LanguageProfile(native="en", target="en", proficiency=Proficiency.A1)


def test_npc_style_profile_without_target_is_valid():
    assert LanguageProfile(native="ja").target is None


def test_learner_needs_target():
    with pytest.raises(ValueError):
        Learner(LanguageProfile(native="en"))
