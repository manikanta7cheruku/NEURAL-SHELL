# 0006: Every action produces a receipt and the reply is reconciled with it

- Status: Accepted
- Date: 2026 (brain v4)

## Context

Seven used to say "Opening Chrome" whether or not Chrome opened. An assistant that operates the computer must never
claim an action it did not perform.

## Decision

Action tags run through `action_receipts.run_action`, which returns success, failed or unconfirmed (with process
verification for known apps). `reconcile_reply` rewrites the reply when an action failed. Receipts are recorded as
outcomes, which feed tool health in the capability registry, and `/api/chat` returns them to the UI.

## Consequences

- Users see the truth, including in the Guide's try-it cards.
- The voice path still uses its own handlers and does not yet produce receipts. This is a known gap, listed in the
  [brain document](../../components/brain.md#known-limitations).
