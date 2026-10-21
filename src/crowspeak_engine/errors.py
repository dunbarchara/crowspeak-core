"""Engine exceptions."""


class ConstraintError(ValueError):
    """A configuration violates an opt-in constraint (e.g. an Npc's `understands`)."""


class UnsupportedSchemaVersion(ValueError):
    """Persisted data was written by a newer engine than this one understands."""
