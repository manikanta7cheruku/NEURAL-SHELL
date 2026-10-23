# Product requirements: Seven 1.x beta

| | |
|---|---|
| Status | Draft for the closed beta |
| Owner | Manikanta Cheruku, Seven Labs |
| Platform | Windows 10 and 11, 64-bit |
| Related | [Overview](overview.md), [Roadmap](roadmap.md), [Architecture](../architecture/overview.md) |

## 1. Goal

Put a private, offline assistant that can operate the PC in the hands of 20 to 50 real users, learn where it fails in
daily use, and reach a quality bar that justifies a public beta.

## 2. Success measures

| Measure | Target for beta exit | How it is measured |
|---|---|---|
| Install success on a clean PC | 95% | Beta survey plus crash reports |
| Commands that do the right thing first time | 90% of instant commands | Action receipts (success vs failed) |
| Time to first spoken or streamed word | Under 1.5 s for instant paths, under 3 s for model replies on a 6 GB GPU | `/api/brain/diagnostics` latency percentiles |
| Day 7 retention | 40% of installs still used on day 7 | Opt-in usage telemetry |
| Crash-free sessions | 99% | Opt-in crash reporting |
| Bug reports answered | Within 48 hours | Feedback sheet |

## 3. Users and core jobs

1. **"Set me up for work."** Restore a saved workspace (apps, windows, tabs) with one sentence.
2. **"Do this small thing for me."** Open, close, arrange, change volume or brightness, find a file, without touching the mouse.
3. **"Don't let me forget."** Tasks, reminders, alarms and timers by voice that fire even when the app is closed.
4. **"Know me."** Remember preferences and context, and show exactly what it knows.
5. **"Answer me."** Conversation and questions from a local model, from the user's own documents, and from the web when online.

## 4. Scope

### In scope (exists today, must be beta quality)

| Area | Requirement |
|---|---|
| Input | Wake word, push to talk (hold Shift), typed Console, interrupt by voice, pause and resume phrases |
| Instant commands | Apps, windows (snap, layouts, pin, transparency, monitors), system controls, files, tasks, schedules, triggers, workspaces, settings by chat, hardware questions |
| Honesty | Every action produces a receipt; failures are reported; offline and unknown are said plainly |
| Memory | Facts with history and provenance; visible and editable on the Memory page; delete everything |
| Productivity | Tasks with due dates and subtasks, schedules with notifications, triggers with phrases and hotkeys, workspaces |
| Knowledge | Add documents and ask about them |
| App | Home screen, Dashboard, Console, Tasks, Schedules, Triggers, Memory, Knowledge, Settings, Plans, Updates, Feedback, Guide; light and dark themes |
| Distribution | Signed installer, in-app updates, licence activation and trial, feedback to the team |

### Out of scope for the beta (on the roadmap)

Screen reading, mouse and keyboard control, multi-step task chains, messaging and email, mobile app, plugins,
languages other than English.

## 5. Functional requirements

- **FR1** Any instant command in the in-app Guide must be routed without the language model. Enforced by
  `tests/test_guide_commands.py`.
- **FR2** An action that failed must never be described as done (`action_receipts.reconcile_reply`).
- **FR3** Actions that are hard to undo must ask for confirmation (`agent.confirm_risky`, on by default).
- **FR4** Questions about state ("is wifi on") must read the state, not change it.
- **FR5** Every setting must be changeable from the UI and by chat, validated by one registry (`brain_settings.SETTINGS`).
- **FR6** The user can see, edit, export and delete everything Seven remembers.
- **FR7** Without the internet, every feature except live lookups, updates, licence activation and feedback works.
- **FR8** Feedback sent offline is queued and delivered later; the UI says "sent" only when it was accepted.
- **FR9** Updates download and install silently and keep all user data.

## 6. Non-functional requirements

| Area | Requirement |
|---|---|
| Privacy | No audio, transcript, file or memory leaves the PC. Outbound calls are limited to the list in [privacy and data](../architecture/privacy-and-data.md). |
| Performance | Instant commands under 300 ms from text to action; model replies stream. |
| Hardware | Runs on 8 GB RAM without a GPU (smaller model); best on a GPU with 6 GB or more VRAM. |
| Reliability | The backend restarts itself if it exits; no data loss on crash. |
| Accessibility | Every page usable by keyboard; text contrast meets WCAG AA in both themes. |
| Quality gates | CI must pass (Python tests, ruff, ESLint, build, version check) before merge. |

## 7. Beta exit criteria

1. All success measures in section 2 met for two consecutive weeks.
2. No open bug that loses data or performs an action the user did not ask for.
3. Installer signed with a code-signing certificate; clean-machine install, update and uninstall verified.
4. Crash reporting live (opt-in) and reviewed weekly.
5. Privacy policy and terms published.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Small local models give weak free conversation | Commands are deterministic; hardware-aware model choice; larger model recommended where possible |
| Speech recognition mishears in noise | Push to talk, noise gates, voice ID, typed fallback |
| Windows SmartScreen blocks an unsigned installer | Code-signing certificate before public beta |
| Automation of the OS can do damage | Confirmation for risky actions, receipts, planned safety shield and voice lock |
| Solo development pace | Strict scope: Phase 1 quality before Phase 2 breadth |

## 9. Open questions

- Pricing currency and payment provider for users outside India.
- Whether the free tier stays local-only forever (current answer: yes).
- Minimum supported GPU and model for the public beta.
