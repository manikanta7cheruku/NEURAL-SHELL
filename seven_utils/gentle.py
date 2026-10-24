"""
seven_utils/gentle.py

Keeps Seven from making Windows feel slow.

    cap_threads()      PyTorch, NumPy and ONNX use every CPU core by default; loading and running the embedding model
                       on 16 cores at once is what made the whole PC stutter at launch. Four is plenty for Seven.
    background(secs)   Run this process at below-normal priority, for good (helper daemons) or for the first
                       seconds of startup while models load (the backend), so whatever the user is doing wins.
"""

import os
import threading

_THREAD_VARS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS")


def cap_threads(n: int = 4) -> None:
    """Must run before NumPy or PyTorch are imported."""
    for var in _THREAD_VARS:
        os.environ.setdefault(var, str(n))


def background(seconds: float = 0.0) -> None:
    """Lower this process's priority; with seconds, return to normal after that long."""
    try:
        import psutil
        proc = psutil.Process()
        proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        if seconds:
            timer = threading.Timer(seconds, lambda: proc.nice(psutil.NORMAL_PRIORITY_CLASS))
            timer.daemon = True
            timer.start()
    except Exception:
        pass
