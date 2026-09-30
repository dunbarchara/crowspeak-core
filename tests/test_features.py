from crowspeak_engine import Features
from crowspeak_engine.features import ResolvedFeatures, resolve_features


def test_default_is_everything_off():
    assert resolve_features() == ResolvedFeatures(expression=False)
    assert resolve_features(None, Features()) == ResolvedFeatures(expression=False)


def test_most_specific_set_value_wins():
    conversation, session = Features(expression=False), Features(expression=True)
    assert resolve_features(conversation, session).expression is False
    assert resolve_features(Features(), session).expression is True  # unset falls through
    assert resolve_features(None, session).expression is True
