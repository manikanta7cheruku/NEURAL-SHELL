# Plans and pricing

Every plan runs entirely on the user's computer. Paid plans raise limits and add extras; they never move data to a
server.

## Source of truth

Limits and prices live in one place: `TIER_FEATURES` and `PRICING` in `license.py`. The Plans page reads them through
`/api/license/pricing` and the brain enforces them through `memory/limits.py` and the route handlers, so the page,
the brain and the enforcement cannot disagree. Change a limit there and everything follows.

## Current tiers

| Feature | Free | Pro | Ultimate |
|---|---|---|---|
| Conversations, facts, tasks, workspaces | Unlimited | Unlimited | Unlimited |
| Triggers | 7 | 77 | Unlimited |
| Schedules | 7 | 77 | Unlimited |
| Recurring schedules | No | No | Yes |
| Knowledge files | 3 | 7 | Unlimited |
| Web lookups per day | 7 | 77 | Unlimited |
| Voice recognition (speaker ID) | No | No | Yes |
| Memory export | No | No | Yes |
| Devices per licence | 1 | 1 | 3 |

## Prices (INR)

| | Monthly | Yearly | Lifetime |
|---|---|---|---|
| Pro | 99 | 699 | 1,299 |
| Ultimate | 199 | 999 | 1,999 |

A 14-day Pro trial is available from the Plans page.

Only limits the code enforces appear here. App aliases, URL shortcuts, custom commands, custom paths and window
control levels were listed before 1.4 but never enforced, so they were removed. Seven still learns spelling
shortcuts on its own (say "camra" once, confirm, and it opens Camera next time); that is not a plan feature.

Only limits that the code enforces appear here. App aliases, URL shortcuts, custom commands, custom paths and
window control levels were listed in earlier versions but never enforced, so they were removed in 1.4.

## How licensing works

- A licence key is validated against the licence server and cached locally with a 30-day offline grace period, so a
  paid user without internet keeps their plan.
- Keys are bound to a device ID; the device limit comes from `max_devices`.
- Details: [licensing and updates](../components/licensing-and-updates.md).

## Open decisions

- International pricing and payment provider.
- Whether recurring schedules should move into Pro (they are a core habit feature).
