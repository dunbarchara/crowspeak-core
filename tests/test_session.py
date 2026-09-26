import pytest

from crowspeak_engine import ConstraintError, InteractionPrefs, LanguageProfile, Npc


def npc(id, **kw):
    return Npc(id=id, name=id, persona="p", language=LanguageProfile(native="ja"), **kw)


def test_converse_is_get_or_create(session):
    a = session.converse(npc("a"))
    assert session.converse(npc("a")) is a
    assert session.converse(npc("b")) is not a


def test_default_npc_speaks_learners_target(session):
    conv = session.converse()
    assert conv.npc.language.native == "ja"
    assert session.converse() is conv


async def test_history_is_per_npc_and_survives_return(session):
    a, b = session.converse(npc("a")), session.converse(npc("b"))
    async for _ in a.send_text("hi"):
        pass
    assert len(a.history) == 2 and b.history == []
    assert len(session.converse(npc("a")).history) == 2


def test_session_prefs_shared_and_mutable(session):
    a = session.converse(npc("a"))
    session.set_prefs(InteractionPrefs("ja", "en"))
    assert a.resolve() == ("ja", "en")
    a.set_prefs(InteractionPrefs(None, "ja"))
    assert a.resolve() == ("ja", "ja")


def test_session_set_prefs_is_atomic_on_constraint_error(session):
    session.converse(npc("strict", understands=frozenset({"ja"})))
    session.set_prefs(InteractionPrefs("ja", "ja"))
    with pytest.raises(ConstraintError):
        session.set_prefs(InteractionPrefs("en", "ja"))
    assert session.prefs == InteractionPrefs("ja", "ja")
