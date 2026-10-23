# 0001: Everything runs on the user's computer

- Status: Accepted
- Date: 2025 (recorded 2026-10-23)

## Context

Seven hears everything said near the computer and can operate the machine. People will only trust that if nothing
they say leaves the device. Cloud assistants also stop working without a connection and depend on a vendor staying
in business.

## Decision

Speech recognition, the language model, memory, documents and all actions run locally. The network is used only for
optional live lookups, updates, licensing, usage statistics and feedback, each listed in
[privacy and data](../privacy-and-data.md).

## Alternatives considered

- **Cloud model with local actions.** Much smarter conversation today, but it breaks the privacy promise and offline use.
- **Hybrid with an opt-in cloud model.** Possible later as a clearly labelled option (roadmap item "Seven Cloud"), never
  the default.

## Consequences

- The quality of free conversation is bounded by what a consumer GPU can run, so commands must not depend on the model.
- Installation is heavier (models, speech engines) and must handle many hardware configurations.
- There is no server cost per user, which makes a lifetime licence viable.
