"""The CLI's saved learner profile: round trips, bad files, and the load-or-setup flow."""

import json

import pytest

from crowspeak_cli import cli
from crowspeak_cli.store import JsonFileLearnerStore, ProfileFileError
from crowspeak_engine import (
    InteractionPrefs,
    LanguageProfile,
    Learner,
    Proficiency,
    Target,
)


def make_learner() -> Learner:
    return Learner(
        LanguageProfile(native="en", target=Target("es-MX", Proficiency.B1)),
        id="learner-1",
        prefs=InteractionPrefs(learner_input_language="en", npc_response_language="es-MX"),
    )


@pytest.fixture
def store(tmp_path):
    return JsonFileLearnerStore(tmp_path / "learner.json")


# --- the store ---------------------------------------------------------------------


def test_missing_file_means_no_profile(store):
    assert store.load_current() is None


def test_save_then_load_round_trips(store):
    learner = make_learner()
    store.save(learner)
    assert store.load_current() == learner
    assert store.load("learner-1") == learner


def test_load_with_another_id_returns_none(store):
    store.save(make_learner())
    assert store.load("someone-else") is None


def test_saved_file_is_indented_json_with_the_nested_target(store):
    store.save(make_learner())
    text = store.path.read_text(encoding="utf-8")
    assert "\n  " in text  # indented, for hand editing
    assert json.loads(text)["language"]["target"] == {"language": "es-MX", "proficiency": "B1"}


def test_save_leaves_no_temp_file_and_replaces_the_old_one(store):
    store.save(make_learner())
    store.save(make_learner())
    assert [p.name for p in store.path.parent.iterdir()] == ["learner.json"]


def test_save_creates_the_parent_directory(tmp_path):
    store = JsonFileLearnerStore(tmp_path / "nested" / "p.json")
    store.save(make_learner())
    assert store.load_current() == make_learner()


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        "[]",
        json.dumps({"schema_version": 1, "id": "x"}),  # missing "language"
        json.dumps({"schema_version": 99, "id": "x", "language": {"native": "en"}}),
        json.dumps(
            {
                "schema_version": 1,
                "id": "x",
                "language": {"native": "en", "target": {"language": "es", "proficiency": "Z9"}},
            }
        ),
    ],
)
def test_unusable_file_raises_naming_the_path_and_is_left_alone(store, content):
    store.path.write_text(content, encoding="utf-8")

    with pytest.raises(ProfileFileError, match="learner.json"):
        store.load_current()

    assert store.path.read_text(encoding="utf-8") == content


# --- load_or_configure -------------------------------------------------------------


def configure_counter():
    calls = []

    def configure():
        calls.append(1)
        return make_learner()

    return configure, calls


def test_first_run_configures_and_saves(store):
    configure, calls = configure_counter()

    learner, loaded = cli.load_or_configure(store, configure=configure)

    assert (loaded, len(calls)) == (False, 1)
    assert store.load_current() == learner


def test_second_run_loads_without_asking(store):
    store.save(make_learner())
    configure, calls = configure_counter()

    learner, loaded = cli.load_or_configure(store, configure=configure)

    assert (loaded, calls) == (True, [])
    assert learner == make_learner()


def test_reset_configures_again_and_replaces_the_file(store):
    old = Learner(LanguageProfile(native="en", target=Target("ja", Proficiency.A1)), id="old")
    store.save(old)
    configure, calls = configure_counter()

    learner, loaded = cli.load_or_configure(store, reset=True, configure=configure)

    assert (loaded, len(calls)) == (False, 1)
    assert store.load_current() == learner != old


def test_reset_recovers_from_an_unusable_file(store):
    store.path.write_text("{broken", encoding="utf-8")
    configure, _ = configure_counter()

    cli.load_or_configure(store, reset=True, configure=configure)

    assert store.load_current() == make_learner()


def test_abandoned_setup_keeps_the_old_profile(store):
    store.save(make_learner())

    def interrupted():
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        cli.load_or_configure(store, reset=True, configure=interrupted)

    assert store.load_current() == make_learner()


def test_unusable_file_without_reset_raises(store):
    store.path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ProfileFileError):
        cli.load_or_configure(store)


# --- the setup prompts -------------------------------------------------------------


def test_configure_learner_saves_the_choices_as_the_learners_prefs(monkeypatch):
    answers = iter(["en", "es-MX", "b1", "native", "target"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    learner = cli.configure_learner()

    assert learner.language == LanguageProfile(native="en", target=Target("es-MX", Proficiency.B1))
    assert learner.prefs == InteractionPrefs(
        learner_input_language="en", npc_response_language="es-MX"
    )
