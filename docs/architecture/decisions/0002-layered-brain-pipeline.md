# 0002: The brain is an ordered pipeline of layers; the model is the last one

- Status: Accepted
- Date: 2025 (recorded 2026-10-23)

## Context

A local 3B to 8B model is too slow and too unreliable to decide whether "set brightness to 100" should change the
screen. Commands need to be instant and exact. Conversation needs a model.

## Decision

`brain.think()` runs a fixed list of layers (`brain_modules/pipeline.py`). Each layer either answers and stops the
pipeline, or adds context and passes on. Deterministic layers (identity, settings, productivity, files, system,
windows, apps, memory recall) run first. The model (`layer_08_llm`) runs last and only when nothing else answered.

## Alternatives considered

- **Model with tool calling for everything.** Flexible, but slow on local hardware and wrong often enough to be unsafe
  for actions. It is planned as an addition for multi-step tasks, not as a replacement.
- **A single intent classifier.** Simpler, but one classifier cannot hold the detail each domain needs.

## Consequences

- Commands answer in milliseconds and can be tested without a model.
- Layer order matters and must be tested (a file search layer once caught "show my tasks").
- Every new phrasing must be handled somewhere, so tests such as `test_guide_commands.py` guard the phrases users see.
