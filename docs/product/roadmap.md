# Roadmap

The long-term plan has eight phases. Each phase makes Seven a more complete layer between the person and their
devices. Version numbers below are the planning labels from the master roadmap; the shipped app version (in
`version.txt`) moves on its own semantic version line (see [release process](../development/release-process.md)).

Status key: **Shipped**, **Partial**, **Next**, **Planned**.

The app shows a short version of this page to users: the Roadmap tab of the welcome card (`frontend/src/lib/roadmap.js`),
in themes without version numbers or dates. When something ships or moves, update both.

## Phase 1: Mind and hands (foundation)

| Item | Status | Notes |
|---|---|---|
| Smart chat with personality | Shipped | Local model through Ollama, personality sliders |
| Long-term memory | Shipped | SQLite facts with history and provenance, semantic index |
| Command log and mood | Shipped | App history, tone tracking |
| Voice identity | Partial | Speaker recognition on the Ultimate plan; per-person memory profiles still to finish |
| Interruption and full duplex | Partial | Interrupt by voice works; true talk-over is not finished |
| Web search and live knowledge | Shipped | Optional, honest when offline |
| App control | Shipped | Open and close by everyday names, verified by receipts |
| Window mastery | Shipped | Snap, layouts, monitors, pin, transparency, undo |
| System control | Shipped | Volume, brightness, Wi-Fi, Bluetooth, media, dark mode, night light, DND, airplane mode |
| Scheduler | Shipped | Reminders, alarms, timers, recurring |
| Velocity (sub 1.5 s replies) | Partial | Streaming and warm model in place; needs measurement on real hardware |
| Offline knowledge base | Partial | Your own documents work; downloadable offline encyclopedia not started |

## Phase 2: Senses (perception and screen control)

Seeing the screen, finding buttons by text, presence detection, gestures, full mouse and keyboard control, screen
reading, smart scrolling, form filling, multi-monitor awareness. **Planned.** This is the phase that turns Seven from
"controls what Windows exposes" into "controls anything on screen".

## Phase 3: Agent (autonomy)

Multi-step plans you approve, self-healing retries, saved routines, writing its own scripts, system monitoring with
alerts, file organisation, context-aware suggestions, a decision engine, day planning, reply drafting in your style,
clipboard and screenshot intelligence, finance and wellness helpers. **Planned.** Routines exist today as triggers and
workspaces.

## Phase 4: Communicator

Messages, calls, notifications and email on desktop and phone, meeting notes and live translation, always with
approval before sending. **Planned.**

## Phase 5: Creator

Social accounts, writing, local image and video generation, scheduling and analytics, document and resume
generation. **Planned.**

## Phase 6: Interface

| Item | Status |
|---|---|
| User console with personality, memory, automation and privacy controls | Shipped (the current desktop app) |
| Avatar, voice cloning, theme engine, widgets | Planned (light and dark themes shipped) |
| Accessibility mode | Planned |

## Phase 7: Ecosystem

Phone as remote, standalone mobile Seven, cross-device sync, wearables, smart home, car, Seven-to-Seven, developer
mode. **Planned.**

## Phase 8: Product

| Item | Status |
|---|---|
| Safety shield (confirmation for risky actions) | Partial: confirmation exists, full shield planned |
| Updates without reinstalling | Shipped (needs end-to-end verification on the Inno installer) |
| Privacy dashboard and delete everything | Partial: Memory page and Settings, export on Ultimate |
| Onboarding wizard | Shipped |
| Multi-language, plugins, marketplace, family sharing, enterprise, education, white label, optional cloud | Planned |
| Backup and restore, security shield (voice lock, encryption at rest) | Planned |
| Performance optimizer | Partial: hardware-aware model choice exists |

## What ships next (in order)

1. **Beta blockers:** code signing, clean-machine install and update test, opt-in crash reporting, measured latency on
   the real model.
2. **Closed beta** with 20 to 50 users, weekly releases from feedback.
3. **Brain quality:** fix known misroutes (for example "switch to Chrome" restoring a workspace, "what do you know about
   me"), wire receipts and confirmations into the voice path, per-person memory.
4. **Phase 2 start:** screen reading (OCR) and click-by-text, the single biggest jump in what Seven can do.
5. **Phase 3 start:** multi-step plans with approval, built on receipts.

## How versions map to releases

| App version | Theme |
|---|---|
| 1.3.x (now) | Beta hardening: brain v4, redesigned app, Guide, docs |
| 1.4 | Closed beta fixes, crash reporting, signed installer |
| 1.5 | Public beta |
| 2.0 | Senses: screen reading and control |
| 3.0 | Agent: multi-step plans |
