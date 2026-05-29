# Piper Voice Models

These voice model files are NOT included in git (too large).
Download them manually before running Seven in development.

## Download Instructions

### Step 1 — Piper Executable
Download: https://github.com/rhasspy/piper/releases/latest
File: piper_windows_amd64.zip
Extract all contents into this folder: mouth/piper/

### Step 2 — Voice Models
Download from: https://huggingface.co/rhasspy/piper-voices/tree/main

| Voice | File | Gender | Language | Path on HuggingFace |
|-------|------|--------|----------|---------------------|
| Ryan  | en_US-ryan-high.onnx + .json | Male | American English | en/en_US/ryan/high/ |
| Amy   | en_US-amy-medium.onnx + .json | Female | American English | en/en_US/amy/medium/ |
| Alan  | en_GB-alan-medium.onnx + .json | Male | British English | en/en_GB/alan/medium/ |
| Maya  | en_IN-maya-medium.onnx + .json | Female | Indian English | en/en_IN/maya/medium/ |

### Step 3 — Final Structure
mouth/
  piper/
    piper.exe
    espeak-ng-data/    ← extracted with piper.exe
    voices/
      en_US-ryan-high.onnx
      en_US-ryan-high.onnx.json
      en_US-amy-medium.onnx
      en_US-amy-medium.onnx.json
      en_GB-alan-medium.onnx
      en_GB-alan-medium.onnx.json
      en_IN-maya-medium.onnx      ← optional
      en_IN-maya-medium.onnx.json ← optional

### Step 4 — Test
cd mouth/piper
echo "Hello I am Seven" | piper.exe --model voices/en_US-ryan-high.onnx --output_file test.wav