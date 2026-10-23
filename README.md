<p align="center">
  <img src="assets/brand/logo.png" alt="Seven" width="96" />
</p>

<h1 align="center">Seven</h1>

<p align="center">
  <strong>The layer between you and your computer.</strong><br />
  Say it or type it, and it happens on your PC. Privately, and without the internet.
</p>

<p align="center">
  <a href="https://github.com/manikanta7cheruku/NEURAL-SHELL/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/manikanta7cheruku/NEURAL-SHELL/actions/workflows/ci.yml/badge.svg" /></a>
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0b5cad" />
  <img alt="Runs locally" src="https://img.shields.io/badge/runs-100%25%20on%20device-2e7d32" />
  <img alt="Version" src="https://img.shields.io/badge/version-1.3.4-6366f1" />
</p>

---

## What Seven is

Computers make you do the translating: five apps to open, windows to arrange, settings to find, a list to check.
Seven sits between you and Windows and does that work for you. It listens, understands, acts on the machine and
remembers what matters, and all of it runs on your own computer.

```
"Set brightness to 100"                      done in milliseconds, no AI guesswork
"Put Chrome and File Explorer side by side"  windows arranged
"Save this workspace as Work"                every app, window and tab remembered
"Remind me to stretch in 20 minutes"         fires even when Seven is closed
"What GPU do I have?"                        read live from your hardware
"Set humor to 40%"                           Seven changes itself
```

## What it can do today

| | |
|---|---|
| **Hands** | Open and close any app, folder or site. Snap, stack and arrange windows across monitors, pin, fade, undo. |
| **System** | Volume, brightness, Wi-Fi, Bluetooth, media, dark mode, night light, do not disturb, airplane mode, battery. |
| **Workspaces and triggers** | Save your whole desktop and restore it with one sentence. Your own phrases and hotkeys run anything. |
| **Files** | Find files by name or by what is inside them, and open the best match. |
| **Tasks and schedules** | To-dos with due dates and subtasks; reminders, alarms and timers that fire with the app closed. |
| **Memory** | Remembers what you tell it, keeps the history when you change your mind, and shows you everything it knows. |
| **Your documents** | Add PDFs, Word, PowerPoint and Excel files and ask questions about them, offline. |
| **Conversation** | A local language model for everything else, honest about what it does not know. |
| **Voice** | Wake word, push to talk, interrupt any time, speaker recognition. Or type in the Console. |

Seven never claims an action worked unless it did: every action returns a receipt, and failures are reported plainly.

## Private by design

Speech recognition, the AI model, memory and documents all run on your computer. Nothing you say is uploaded. Seven
connects to the internet only for things you would expect: live lookups such as weather when you ask, update checks,
licence activation, anonymous usage minutes (can be turned off in Settings) and feedback you choose to send. The full
list, from the code, is in [privacy and data](docs/architecture/privacy-and-data.md).

## How it works

```
 microphone / keyboard
        |
      ears           noise handling, wake word, speech-to-text (faster-whisper), voice ID
        |
      brain          ordered layers: commands and memory answered instantly,
        |            a local model (Ollama) only when nothing else can answer
        |
  hands + mouth      actions on Windows with receipts, natural speech (Piper)
        |
      memory         SQLite facts with history and provenance, semantic index
```

Read the [architecture overview](docs/architecture/overview.md) and the [brain](docs/components/brain.md) for depth.

| Layer | Technology |
|---|---|
| Desktop shell | Electron |
| Interface | React, Vite, Tailwind CSS |
| Backend | Python 3.11, FastAPI on localhost |
| Language model | Ollama (model chosen for your hardware) |
| Speech | faster-whisper, Silero VAD, Piper TTS, TitaNet speaker ID |
| Memory | SQLite (FTS5), ChromaDB, sentence-transformers |
| Installer | Inno Setup |

## Get Seven

Download the latest installer from
[Releases](https://github.com/manikanta7cheruku/seven-releases/releases/latest) and run it. The setup wizard
installs the AI runtime and a model that fits your computer. After that, Seven updates itself.

| | Minimum | Recommended |
|---|---|---|
| OS | Windows 10, 64-bit | Windows 11 |
| Memory | 8 GB RAM | 16 GB RAM |
| Graphics | Not required | NVIDIA with 6 GB VRAM or more |
| Disk | 10 GB free | 20 GB free |

## Plans

Seven is free to use, fully local, on every plan. Pro and Ultimate raise limits on triggers, schedules and documents
and add extras such as speaker recognition. See [plans and pricing](docs/product/plans-and-pricing.md).

## Where it is going

Seven is in beta hardening ahead of a closed beta. Next on the [roadmap](docs/product/roadmap.md): reading the screen
and clicking by name, multi-step tasks you approve, a phone companion and plugins.

## Documentation

| | |
|---|---|
| [Docs home](docs/README.md) | Everything, organised |
| [Product overview](docs/product/overview.md), [PRD](docs/product/prd.md), [Roadmap](docs/product/roadmap.md) | What and why |
| [Architecture](docs/architecture/overview.md), [Decisions](docs/architecture/decisions/README.md) | How it fits together |
| [Components](docs/components/README.md) | Brain, ears, mouth, hands and the rest |
| [Development setup](docs/development/setup.md), [Testing](docs/development/testing.md), [Releases](docs/development/release-process.md) | Working on Seven |
| [HTTP API](docs/reference/http-api.md) | Every local endpoint (generated) |

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md). To report a vulnerability, follow [SECURITY.md](SECURITY.md).

## License

Seven is proprietary software by Seven Labs. The source is visible here for transparency; it is not open source.
See [LICENSE.txt](LICENSE.txt).
