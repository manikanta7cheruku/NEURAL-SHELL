# Companion (Seven as a friend)

| | |
|---|---|
| Status | Complete for the first version (messages, thread, pace, quiet hours, voice when idle, learning from answers) |
| Code | `companion/` (`settings.py`, `store.py`, `content.py`, `engine.py`, `scheduler.py`), `backend/routes/companion.py`, `frontend/src/stores/useCompanion.js`, `frontend/src/components/CompanionSettings.jsx`, `CompanionIntro.jsx` |
| Tests | `tests/test_companion.py` |
| Related | [Brain](brain.md) (answers in the thread), [Memory](memory.md) (where answers are kept), [Voice](voice.md) (the greeting, the voice loop) |

Seven reaches out the way a new friend does: it asks about you, tells you about itself and where it is going, shares a
small fact, checks in when you seem down, and follows up on what you told it, even when you have not said anything. It
replaces the old silence watcher, which said a canned line after five quiet minutes.

## What the person sees

- **One thread, called Seven**, pinned at the top of the Chat page's list of chats, with an unread count. It is an ordinary
  conversation (kind `companion`), so anything typed in it is answered by the normal brain, memory and product knowledge
  included. A voice chat never lands in it (`current_conversation` skips it), and it is never auto-renamed.
- **Messages written there, said aloud only when idle.** A small speaker icon marks a message Seven said.
- **Seven asks back.** A moment after answering in the thread it asks one thing, as a second message. If the answer was
  about their job, the next question goes deeper ("What do you enjoy most about it?"). If the answer already ends with a
  question, it asks nothing more.
- **On opening Seven**, after the greeting, anything written but not yet said is said ("I left you a note while you were
  away."). If something is unread, Chat opens on Seven's thread first. The home screen shows "1 new from Seven".
- **Settings in the thread's gear** (and nowhere else): on or off, pace (Natural, Calm, Lively), say aloud, quiet hours,
  topics (about you, about Seven, did you know), and "Quiet for an hour" / "Rest of today". "Ask me something" writes one
  message now.
- Telling Seven "not now" or "stop asking" in the thread gives three hours of quiet.

## What it says

Three banks written by hand (no model), plus things that come from what Seven knows:

| Kind | Source | Cool-down before it can return |
|---|---|---|
| About you | 16 questions: work, music, food, travel, what you are learning, how your day was (morning and evening ones only at those times) | 60 days |
| About Seven | 15 questions: what it will become, privacy, workspaces, reminders, triggers, memory, voices, phone, languages; each ends with a question | 21 days |
| Did you know | 16 true, timeless facts, each with a light question | 90 days |
| Goal follow-up | "How is learning Rust going?" for an active goal (`learning_store.list_goals`) | 4 days |
| A held-back question | `learning_store.next_gap` through the curiosity templates | 14 days |
| Care | "You seemed a bit off earlier..." when the mood label is frustrated or down | 1 day |
| Welcome back | after ten hours or more away | none |

Choosing (`content.pick`): care and welcome first; otherwise nothing asked recently, things that suit the time of day, a
different kind from the last two, and a weighted random choice, so it never feels like a fixed rotation. Now and then the
name is used (30 percent), never twice in one message.

A short answer to a "you" question is remembered as a fact in the normal memory (`Does or studies: teacher`), and the
deeper question is queued. A "no", a question back, or a long message is a conversation, not an answer. A spoken reply
within four minutes of a question counts as its answer.

## When it reaches out (`scheduler.py`)

A friend does not message on a timer, so the rules are about the person:

| Rule | Value |
|---|---|
| How many a day | `auto`: 3, 5 or 7, fixed by the date (5 is likelier); `calm`: 3; `lively`: 7 |
| Gap between messages | `auto` 7 to 17 minutes, `calm` 14 to 30, `lively` 7 to 12; doubled once two went unanswered, none after three |
| Quiet hours | none from the start to the end time set in the chat settings (default 22:00 to 08:00) |
| Never | while snoozed, while Seven is speaking or thinking, in the first four minutes after launch, while you type or use the mouse (under 20 s idle), or within 90 s of talking to Seven |
| One at a time | a message waiting to be said blocks writing another |
| Said aloud | only when you have paused (20 s or more) but are still at the PC (under ten minutes idle), and not in a conversation with Seven. Away: written, not said, until you are back |
| On launch | anything unsaid is said after the greeting, up to three at once |

`tick()` runs every 15 seconds on a daemon thread; time, idleness and speaking are arguments, so the tests drive it
exactly. Idleness comes from Windows (`GetLastInputInfo`) and from `scheduler.touch()` (called when you type in the
thread or speak to Seven).

## Data

`companion.db` next to the chats: `sent` (each message, how it was delivered, read, answered), `asked` (when each topic
was last asked), `state` (next allowed time, snooze, the queued deeper question, last seen). The messages themselves are
in `conversations.db`. Nothing leaves the PC.

## HTTP

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/companion/state` | The thread's id, unread, settings, today's count and target, snooze |
| POST | `/api/companion/read` | The thread was opened |
| POST | `/api/companion/snooze` | `{"minutes": 60}`; 0 ends it |
| POST | `/api/companion/nudge` | "Ask me something" |

Settings are ordinary config (`companion` in `config.json`, saved with `PUT /api/config`).

## Not built yet

- **A tray helper** that lets Seven message you when its window is closed. Today Seven writes and speaks only while it is
  running; what it wrote while you were away is said when you are back or when you reopen it.
- **News.** A real daily news line needs a source and the internet. The "did you know" bank is offline and timeless.
- **Fullscreen and meeting detection.** "Idle" means no input for 20 seconds; a video you are only watching can look
  idle. Quiet hours and "Quiet for an hour" cover it for now.
