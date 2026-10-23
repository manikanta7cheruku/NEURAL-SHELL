# Product overview

## One sentence

Seven is the layer between you and your computer: you say what you want, and it happens on your PC, privately and
without needing the internet.

## The problem

Computers make people do the translating. To "get ready for work" you open five apps, find the right tabs, arrange
windows, turn on do not disturb and check your list. Every one of those is a small, learnable sequence of clicks,
and every one of them is repeated daily.

Voice assistants were supposed to fix this, but they live in the cloud and stop at the edge of the operating system.
Siri, Alexa and Google Assistant answer questions and control phones and smart speakers. Copilot is tied to Microsoft
services and a subscription. None of them can reliably arrange your windows, restore your workspace, find the file you
saved last week or run your own routines, and all of them send what you say to a server.

## What Seven is

Seven sits between the person and the operating system:

```
        You (voice or text)
               |
             Seven      understands the request, remembers context, decides what to do
               |
   Windows: apps, windows, settings, files, notifications, hardware
```

- **It acts.** Opening, closing and arranging apps, system controls, files, workspaces, reminders and tasks are done
  directly, in milliseconds, without asking a language model to guess.
- **It understands.** A local language model handles conversation and anything that is not a direct command.
- **It remembers.** Facts you tell it, how you like it to talk and what you were working on, with the evidence for each.
- **It is honest.** It says when something failed, when it is offline and when it does not know.
- **It is private.** Speech recognition, the model and memory run on the computer. Nothing you say is uploaded.
- **It works offline.** Only live lookups (weather, news), updates, licence activation and feedback need a connection.

## Who it is for

| Person | What they get first |
|---|---|
| Busy professional | One sentence restores the work setup; tasks and reminders by voice |
| Student | Focus workspace, timers, reminders, answers from their own documents |
| Developer and power user | Window layouts, triggers and hotkeys, file search, local models they control |
| Privacy-conscious user | An assistant that never sends their voice or data anywhere |
| Accessibility needs | Control of the PC by voice (deeper accessibility mode is on the roadmap) |

## Principles

1. **Local first.** The product must work with the network cable unplugged.
2. **Act, then prove it.** An action is reported as done only when a receipt says it worked.
3. **Evidence before assertion.** Personal facts come from what the user said, never from the model's imagination.
4. **Deterministic where it matters.** Commands, time, identity and abilities are code paths, not model output.
5. **Ask before anything risky.** Closing everything or switching on airplane mode waits for a yes.
6. **The user owns the data.** Everything is visible, editable, exportable and deletable from the app.

## Positioning

| | Seven | Cloud assistants (Siri, Alexa, Google) | Copilot | ChatGPT desktop |
|---|---|---|---|---|
| Runs on the device | Yes | No | Partly | No |
| Works offline | Yes | No | No | No |
| Controls apps, windows and settings | Yes | Limited | Limited | No |
| Remembers you with visible evidence | Yes | Limited | Limited | Yes, in the cloud |
| Your voice leaves the device | Never | Yes | Yes | Yes |
| Paid tiers | One-time or subscription, core is free | Free with data use | Subscription | Subscription |

## Where it stands today

Version 1.3.x is a working desktop product for Windows 10 and 11: voice and text, the instant command layers, memory,
tasks, schedules, triggers and workspaces, documents, a full settings surface, licensing and in-app updates. The next
milestone is a closed beta. See the [PRD](prd.md) for beta scope and exit criteria and the [roadmap](roadmap.md) for
what follows.
