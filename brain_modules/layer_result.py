"""
=============================================================================
brain_modules/layer_result.py

Return type for every layer in the brain pipeline.

Each layer's process() method returns a LayerResult telling the pipeline what to do:
    - stop(response)          → pipeline stops, brain.think() returns this response
    - stop_stream(generator)  → pipeline stops, returns streaming tuple to main.py
    - pass_through()          → continue to next layer
    - modify_context(...)     → mutate context, continue to next layer

WHY THIS PATTERN:
    Explicit control flow. No hidden returns from deep inside layer functions.
    Every layer's outcome is one of 4 clear cases.
    Debugging is trivial — trace which layer stopped the pipeline.
=============================================================================
"""


class LayerResult:
    """Immutable result object returned by every pipeline layer."""

    __slots__ = ("action", "response", "generator")

    def __init__(self, action, response=None, generator=None):
        self.action    = action     # "stop", "stop_stream", "pass"
        self.response  = response   # str for "stop"
        self.generator = generator  # generator for "stop_stream"

    @classmethod
    def stop(cls, response):
        """Halt pipeline. brain.think() returns this response string."""
        return cls("stop", response=response)

    @classmethod
    def stop_stream(cls, generator):
        """Halt pipeline. brain.think() returns ('__STREAM__', generator)."""
        return cls("stop_stream", generator=generator)

    @classmethod
    def pass_through(cls):
        """Continue to next layer."""
        return cls("pass")

    @property
    def is_stop(self):
        return self.action in ("stop", "stop_stream")