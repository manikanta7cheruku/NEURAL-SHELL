"""
test_stage1a.py
Verify Stage 1A dependencies installed correctly.
"""

import sys

def check(name, import_stmt):
    try:
        exec(import_stmt)
        print(f"  [OK]   {name}")
        return True
    except Exception as e:
        print(f"  [FAIL] {name} -> {e}")
        return False

print("=" * 60)
print("STAGE 1A DEPENDENCY CHECK")
print("=" * 60)
print()

results = []
results.append(check("tensorflow",     "import tensorflow as tf; print('    version:', tf.__version__)"))
results.append(check("tensorflow_hub", "import tensorflow_hub as hub"))
results.append(check("librosa",        "import librosa; print('    version:', librosa.__version__)"))
results.append(check("soundfile",      "import soundfile as sf"))
results.append(check("numpy",          "import numpy as np"))
results.append(check("pyaudio",        "import pyaudio"))

print()
print("=" * 60)
if all(results):
    print("STAGE 1A COMPLETE — All dependencies installed")
    sys.exit(0)
else:
    print("STAGE 1A FAILED — Fix errors above before continuing")
    sys.exit(1)