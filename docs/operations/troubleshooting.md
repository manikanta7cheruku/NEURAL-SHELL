# Troubleshooting

## Where to look first

| Signal | Where |
|---|---|
| Is the backend up | `http://127.0.0.1:7777/api/health` |
| What Seven is doing | `http://127.0.0.1:7777/api/status` |
| Brain health, model, latency | `http://127.0.0.1:7777/api/brain/diagnostics` |
| Which layer answered a message | the `done` event of `/api/chat`, field `answered_by` |
| Backend logs | the console that runs `main.py` (development) or the app's log file (`paths.log_file`) |

## Common problems

| Symptom | Likely cause | Fix |
|---|---|---|
| App stuck on "Loading configuration" | Backend still starting or crashed | It retries for 30 seconds. Check `/api/health`; restart Seven |
| Port 7777 already in use | Another copy of Seven, or a dev backend, is running | Quit the other copy (tray, Quit) |
| Seven does not hear me | Wrong microphone, threshold too high | Settings, Voice. Try holding Shift to talk |
| Wakes up on its own | Noise or TV | Raise the listening threshold; turn on voice recognition (Ultimate) |
| First reply is slow | Model not loaded yet or running on CPU | Wait for warm-up; choose a smaller model in Settings, Brain |
| "I tried ... but it didn't work" | The action failed and Seven is reporting it honestly | Read the reason in the reply; try the full app name |
| Opens the wrong app | Name matches something else | Say the full name once and confirm the correction |
| Live questions say "offline" | No internet, or web lookups switched off | Settings, Privacy & data |
| Feedback shows "queued" | Offline, or the form is unreachable | It is sent automatically when online |
| Update never arrives | Server asleep or GitHub rate limit | Updates page, "Check now" |
| Memory answers about deleted facts | Index not reconciled yet | Restart; run `scripts/memory_doctor.py --fix` |

## Collecting information for a bug report

1. The exact words said or typed.
2. The reply and whether an action happened.
3. `/api/brain/diagnostics` output.
4. Seven version (Updates page) and Windows version.

Send it through the Feedback page.
