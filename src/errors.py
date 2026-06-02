"""Error types for the E-- deterministic core."""


class EmmSyntaxError(Exception):
    """Raised for any syntax violation in canonical E-- source."""
    pass


class EmmResolveError(Exception):
    """Raised when a {{ }} LLM value slot cannot be resolved.

    Covers a missing API key on a cache miss and model output that is not a
    valid Python expression.
    """
    pass
