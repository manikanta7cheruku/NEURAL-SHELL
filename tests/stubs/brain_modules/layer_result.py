"""Test stub used only when the real brain_modules/layer_result.py is absent (standalone runs)."""


class LayerResult:
    __slots__ = ("action", "response", "generator")

    def __init__(self, action, response=None, generator=None):
        self.action, self.response, self.generator = action, response, generator

    @classmethod
    def stop(cls, response):
        return cls("stop", response=response)

    @classmethod
    def stop_stream(cls, generator):
        return cls("stop_stream", generator=generator)

    @classmethod
    def pass_through(cls):
        return cls("pass")

    @property
    def is_stop(self):
        return self.action in ("stop", "stop_stream")
