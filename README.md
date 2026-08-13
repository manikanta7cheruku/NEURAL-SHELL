# Seven

A voice assistant that runs entirely on your Windows PC.

No cloud. No subscription required for core features. No data sent anywhere.
Seven listens, thinks, and acts using models running locally on your hardware.

---

## What it does

Seven understands natural language and takes real action on your computer.

You speak (or type). Seven processes your request locally using Ollama and a
local language model. Then it responds with voice and executes the action —
whether that is launching an app, setting a reminder, managing your tasks,
searching your files, or answering a question.

Everything stays on your machine.

---

## Core capabilities

**Voice control**
Wake word detection, push-to-talk mode, speaker verification, interrupt
mid-response, pause and resume with natural phrases.

**Task management**
Create, complete, and track tasks by voice. Subtasks, due dates, priorities,
and a full task panel accessible via Alt+Shift+T at any time.

**Schedules and reminders**
Set reminders, alarms, timers, and recurring events by voice. Fires overlay
notifications and speaks the alert even when the main window is closed.

**System control**
Launch and close apps, control volume and brightness, snap windows, search
files, take screenshots, check battery — all by voice.

**Persistent memory**
Seven remembers facts you tell it across sessions using a local vector
database. Upload your own documents and ask questions from them.

**Triggers and workspaces**
Map a voice phrase or hotkey to any action. Save a full app layout as a
workspace and restore it in one command.

**Always-on status orb**
A small floating indicator shows Seven's current state at all times.
Click it to open the dashboard. Right-click for the navigation menu.

---

## How it works
You speak
→ Microphone → Noise filtering → Speech to text
→ 13-layer processing pipeline
→ Local LLM via Ollama (if no direct action matched)
→ Voice response + system action

text


The pipeline checks your request against direct action handlers before
reaching the language model. App launches, task creation, and system commands
fire instantly without waiting for the AI.

---

## Tech stack

| Layer       | Technology                              |
|-------------|----------------------------------------|
| Shell       | Electron                               |
| Frontend    | React, Vite, Tailwind CSS              |
| Backend     | Python 3.11, FastAPI, Uvicorn          |
| AI          | Ollama (LLaMA 3, Phi-3, Qwen, TinyLlama) |
| Memory      | ChromaDB (local vector database)       |
| Storage     | SQLite, JSON                           |
| Voice in    | SpeechRecognition, PyAudio             |
| Voice out   | Piper TTS (local neural voices)        |
| Audio       | VAD, AEC, AGC, noise floor calibration |

---

## Hardware requirements

| Component | Minimum              | Recommended           |
|-----------|----------------------|-----------------------|
| OS        | Windows 10 x64       | Windows 11 x64        |
| RAM       | 8 GB                 | 16 GB                 |
| GPU       | 4 GB VRAM (optional) | 6+ GB VRAM (NVIDIA)   |
| Storage   | 10 GB free           | 20 GB free            |
| CPU       | 4 cores              | 8+ cores              |

Seven runs without a GPU. The language model falls back to CPU inference,
which is slower but fully functional.

---

## Getting started

**Download the installer** from the
[Releases](https://github.com/manikanta7cheruku/seven-releases/releases/latest)
page and run it. The setup wizard handles everything: Ollama installation,
model download, and initial configuration.

**First launch takes a few minutes** while the selected language model
downloads. This is a one-time step.

---

## Manual setup (development)

```bash
git clone https://github.com/manikanta7cheruku/seven-releases.git
cd seven-releases

python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

cd frontend
npm install
npm run dev
Install Ollama from ollama.com and pull a model:

Bash

ollama pull llama3
Start Seven:

Bash

python main.py
Privacy
Seven is designed so your data never has to leave your machine.

Data	Stored	Location
Voice audio	Never	Processed in memory
Conversations	Local only	ChromaDB on your PC
User facts	Local only	ChromaDB on your PC
Tasks, schedules	Local only	SQLite on your PC
AI responses	Never sent	Generated locally
Usage statistics	Not collected	
Internet is only used for web search (when you explicitly ask), update
checks (GitHub releases, no data sent), and optional feedback submission.

Global shortcuts
Shortcut	Action
Alt + S	Show or hide Seven window
Alt + Shift + T	Open floating task panel
Shift (hold)	Push to talk (when enabled)
Plans
Seven is free to use with core features.

Pro and Ultimate plans unlock higher limits on memory, schedules, triggers,
and knowledge files. See the Plans page inside the app.

License
Seven is proprietary software. See LICENSE.txt for terms.

Contact
Built by Manikanta Cheruku.
Feedback and bug reports: use the Feedback section inside the app.