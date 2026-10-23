# 0003: Run language models through Ollama

- Status: Accepted
- Date: 2025 (recorded 2026-10-23)

## Context

Seven needs to download, run and switch local models on very different machines, from CPU-only laptops to 8 GB GPUs.

## Decision

Use Ollama as a separate local service on `127.0.0.1:11434`. `brain_manager.py` picks a model for the hardware.
`ollama_client` keeps one pooled connection, pins the model in memory and streams tokens.

## Alternatives considered

- **llama.cpp embedded in the Python process.** Fewer moving parts, but model management, GPU detection and updates
  would all be ours to maintain.
- **ONNX Runtime.** Strong on NPUs (useful for a future mobile version), with weaker model availability today.

## Consequences

- Setup must install Ollama and pull a model. The setup wizard handles this.
- The model is a user setting and can be changed by chat.
