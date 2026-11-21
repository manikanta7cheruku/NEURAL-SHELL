"""
ears/gpu_guard.py
A graphics card that loads the speech model but cannot run it.

CTranslate2 reports a CUDA device as soon as the NVIDIA driver is there, and the model loads on it, but running it needs the CUDA
libraries (cuBLAS, cuDNN). On a PC without them the first transcription fails with "Library cublas64_12.dll is not found", and so does
every one after it: Seven hears, finds no words, and ignores everything as "transcription failed". Seven now recognises that kind
of failure, switches to the processor for good, and says so in the log, instead of failing for ever.
"""

_MARKERS = ("cublas", "cudnn", "cudart", "cuda", "out of memory", "no kernel image", "driver version")


def is_gpu_error(exc) -> bool:
    """Is this exception the graphics card failing to run the model (and not, say, a bad audio array)?"""
    text = f"{type(exc).__name__} {exc}".lower()
    return any(marker in text for marker in _MARKERS)
