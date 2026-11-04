# Diagnostics: finding out what is wrong on someone else's PC

One report collects what we would otherwise have to ask a friend, one question at a time. It is plain text; nothing personal is
in it (no name, email, files or conversations, and the Windows user name is replaced).

## Getting the report

Pick whichever works for the person:

| Situation | How |
|---|---|
| Seven opens | Settings, System, **Diagnostics**, Run diagnostics, **Copy report** |
| Seven is open but you only have a browser | open `http://127.0.0.1:7777/api/diagnostics/report` and copy the page (it takes up to half a minute) |
| Right click the voice bar or the tray icon | **Diagnostics report** opens the same page |
| Seven will not start at all | Start menu, **SEVEN Diagnostics**: writes `Seven-Diagnostics.txt` to the Desktop, copies it and opens it |
| From source | `python backend/diagnostics.py` |

## Reading it

The top lists everything that failed or looks wrong ("READ THESE FIRST"); the rest is the detail by section.

| Section | What it tells you |
|---|---|
| Live state | whether Seven finished loading, whether it is listening, any hearing problem or safe mode |
| Safe mode | failed starts in a row and the reason |
| Microphone | Windows' microphone privacy switches, the microphones found, the state of the stream |
| Speech recognition | whether the ears loaded, which speech models are on the PC, GPU or processor |
| Native libraries | each speech and audio library imported in a child process: a library that crashes on this PC (an old processor, a missing Visual C++ runtime) shows up here and not as a dead Seven |
| Network and server | the Seven server (and how long it took to wake), Hugging Face, GitHub, and whether the PC is on the server's user list |
| Logs | the last warnings from `seven.log`, `native_crash.log` and `python_crash.log` |

## Seven tells you itself: Settings, System, Hearing

Nobody has to run anything. When Seven is not hearing you the home screen says why and what to do ("Seven hears you but waits for
'Hey Seven'. Say it first, or choose Always on"), and Settings, System, **Hearing** shows it live:

- a **microphone level** bar and a **speech found** bar with a mark where the voice detector starts counting sound as you talking:
  speak and watch. If the level does not move, Seven is not receiving your voice; if it moves and the speech bar crosses the mark,
  it hears you and the list says what happens to it next;
- the listening mode, and whether the voice loop is running or stuck;
- the problems found, each with what was seen and what to do, and the last sounds it picked up and what became of them.

The same findings are written to `%APPDATA%\SEVEN\logs\hearing_debug.log` whenever they change, with the numbers behind them, and
the Diagnostics report includes them, so a report from a friend says what went wrong and when. The logic is `ears/doctor.py`.

Some laptop microphone arrays (AMD's, among others) apply a noise gate and send exact silence until someone speaks, so silence
alone is not called a fault; Seven looks for another microphone only after a minute of silence when the current one has not been
heard carrying speech since it started.

## "Listening" but nothing happens

The report has two sections for this, **Hearing right now** and **Voice loop**, and there is a standalone check for when you
need more.

| The report says | It means | What to do |
|---|---|---|
| `Microphone level ... SILENT` | the microphone delivers no sound at all (muted at the hardware, a driver that gives nothing, the wrong device) | unmute (many laptops have a mute key), pick the right device in Windows Sound settings, Input. Seven also tries the other microphones itself after 8 seconds of digital silence and says which one it switched to |
| `very quiet` | sound arrives, but too faintly for the voice detector | raise the microphone volume in Windows Sound settings, Input |
| `Voice detector ... finds no speech` | the sound is noise, or heavy noise suppression flattens speech | speak closer, try sensitivity Relaxed, try another microphone |
| `Last N things it heard: ... no wake word x9` | Wake word mode: Seven acts only after "Hey Seven" | say it, or choose Always on |
| `Seven's own voice` many times, or `Seven speaking for 400 s` | Seven believes it is talking, so it throws away everything it hears | headphones; restart Seven; send the report |
| `Push to talk` | Seven hears only while Shift is held | choose Always on or Wake word |
| `Mode on screen ... differs` or `Voice loop STUCK` | the loop that acts on what is heard stopped; the report prints the line it is waiting at | send the report |

**Microphone check** (`backend/ear_check.py`, Start menu, "SEVEN Microphone Check") works without Seven: quit Seven, run it,
and say "Hey Seven, what time is it" when it asks. It records six seconds, then prints the level per second, the voice
detector's score, what the speech model transcribed and the reason Seven would give for ignoring it, and saves
`Seven-Mic-Check.txt` on the Desktop (and copies it). On a PC that has an older Seven installed (no Start menu entry), send two files, `backend\ear_check.py` and
`scripts\Seven-Mic-Check.bat`, and have the person put them in one folder, quit Seven (tray icon, right click, Quit SEVEN) and
double-click the `.bat`. Or in PowerShell (not Command Prompt: `%VAR%` does not work there), from the folder holding the file:

```
& "$env:LOCALAPPDATA\Programs\SEVEN\resources\app\python\python.exe" .\ear_check.py
```

## Safe mode

Seven starts without its speech and brain only after **three failed starts in a row**. One failure just tries again on the
next start, an update clears the record, and a good start clears it too. The home screen says why and has a **Try again**
button (`POST /api/safe-mode/retry`). Before this, one failed start was permanent: Seven sat on "Getting ready", could not
hear, and the test mic answered "not listening", with no error anywhere.

## Users who do not appear in the admin dashboard

A person appears once the server has their name and email. The server sleeps when idle and takes up to a minute to wake,
so registration (`telemetry.register_in_background`) wakes it, waits, and keeps retrying with growing pauses until the server
confirms; it then sends again only if the name or email changes. The report says whether this PC is registered and, if not,
why. To stop the server sleeping, point a free uptime monitor at `https://<your-server>/ping` every 5 minutes.
