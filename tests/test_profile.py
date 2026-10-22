import pytest

from crowspeak_engine import LanguageProfile, Learner, Proficiency, Target


def test_native_and_target_must_differ():
    with pytest.raises(ValueError):
        LanguageProfile(native="en", target=Target("en", Proficiency.A1))


def test_npc_style_profile_without_target_is_valid():
    assert LanguageProfile(native="ja").target is None


def test_learner_needs_target():
    with pytest.raises(ValueError):
        Learner(LanguageProfile(native="en"))


def test_learner_target_is_never_none():
    learner = Learner(LanguageProfile(native="en", target=Target("es-MX", Proficiency.B1)))
    assert learner.target == Target("es-MX", Proficiency.B1)


@pytest.mark.parametrize(
    "profile",
    [
        LanguageProfile(native="ja"),
        LanguageProfile(native="en", target=Target("es-MX", Proficiency.B2)),
    ],
)
def test_profile_round_trips_through_dict(profile):
    assert LanguageProfile.from_dict(profile.to_dict()) == profile


def test_serialized_target_is_one_nested_object():
    profile = LanguageProfile(native="en", target=Target("es-MX", Proficiency.B1))
    assert profile.to_dict() == {
        "native": "en",
        "target": {"language": "es-MX", "proficiency": "B1"},
    }
    assert LanguageProfile(native="ja").to_dict() == {"native": "ja", "target": None}
