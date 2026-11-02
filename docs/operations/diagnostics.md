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
