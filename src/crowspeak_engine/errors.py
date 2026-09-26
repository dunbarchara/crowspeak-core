"""Engine exceptions."""


class ConstraintError(ValueError):
    """A configuration violates an opt-in constraint (e.g. an Npc's `understands`)."""
