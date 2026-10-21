import pytest

from crowspeak_engine import (
    Engine,
    Features,
    InMemoryLearnerStore,
    InteractionPrefs,
    LanguageProfile,
    Learner,
    Proficiency,
    UnsupportedSchemaVersion,
)


def _full_learner() -> Learner:
    return Learner(
        LanguageProfile(native="en", target="es-MX", proficiency=Proficiency.B1),
        id="learner-1",
        prefs=InteractionPrefs(learner_input_language="en", npc_response_language="es-MX"),
        features=Features(expression=True, corrections=False),
    )


def test_round_trip():
    learner = _full_learner()
    assert Learner.from_dict(learner.to_dict()) == learner


def test_round_trip_without_optional_fields(learner):
    assert Learner.from_dict(learner.to_dict()) == learner


def test_payload_without_optional_keys():
    data = {
        "schema_version": 1,
        "id": "learner-1",
        "language": {"native": "en", "target": "es-MX", "proficiency": "A2"},
    }
    learner = Learner.from_dict(data)
    assert learner.prefs is None and learner.features is None
    assert learner.language.proficiency is Proficiency.A2


def test_unknown_keys_are_ignored():
    data = _full_learner().to_dict()
    data["something_new"] = {"a": 1}
    data["language"]["something_new"] = True
    assert Learner.from_dict(data) == _full_learner()


def test_newer_schema_version_is_rejected():
    data = _full_learner().to_dict()
    data["schema_version"] = 2
    with pytest.raises(UnsupportedSchemaVersion, match="schema_version 2"):
        Learner.from_dict(data)


def test_payload_without_target_is_rejected():
    data = _full_learner().to_dict()
    data["language"] = {"native": "en", "target": None, "proficiency": None}
    with pytest.raises(ValueError):
        Learner.from_dict(data)


def test_store_load_missing_returns_none():
    assert InMemoryLearnerStore().load("nope") is None


def test_store_save_and_load():
    store = InMemoryLearnerStore()
    learner = _full_learner()
    store.save(learner)
    assert store.load("learner-1") == learner


def test_store_save_overwrites():
    store = InMemoryLearnerStore()
    store.save(_full_learner())
    updated = Learner(
        LanguageProfile(native="en", target="es-MX", proficiency=Proficiency.B2), id="learner-1"
    )
    store.save(updated)
    assert store.load("learner-1") == updated


def test_store_holds_serialized_data():
    store = InMemoryLearnerStore()
    store.save(_full_learner())
    loaded = store.load("learner-1")
    assert loaded is not store.load("learner-1")


def test_learner_features_are_defaults_under_session_and_conversation(llm):
    learner = _full_learner()
    session = Engine(llm).start_session(learner)
    conv = session.converse()
    assert conv.resolved_features().expression is True

    session.set_features(Features(expression=False))
    assert conv.resolved_features().expression is False

    conv.set_features(Features(expression=True))
    assert conv.resolved_features().expression is True
    # not set at any override layer, so the learner's default still applies
    assert conv.resolved_features().corrections is False


def test_learner_prefs_fill_fields_a_session_override_leaves_unset(llm):
    learner = _full_learner()
    session = Engine(llm).start_session(learner, InteractionPrefs(learner_input_language="es-MX"))
    assert session.converse().resolve() == ("es-MX", "es-MX")
    session.set_prefs(InteractionPrefs(npc_response_language="en"))
    assert session.converse().resolve() == ("en", "en")
