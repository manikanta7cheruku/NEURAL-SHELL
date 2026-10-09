# Small patches to files that are not replaced

These files are large and mostly correct, so they are patched instead of replaced.
Each patch is a few lines.

## 1. backend/api_server.py  (register the diagnostics route)

Add next to the other route imports:

    from backend.routes import brain as brain_routes

Add next to the other `app.include_router(...)` lines:

    app.include_router(brain_routes.router)

## 2. brain_modules/dialogue_manager.py  (stops "what is 2 plus 2" opening a file)

Bug: after any file search, bare number words and digits in short inputs were treated as
"open result #N". Even the name "seven" counted as the 7th result.

In `_REFERENCE_ORDINALS` delete these entries: "one", "two", "three", "four", "five",
"six", "seven", "eight", "nine", "ten" (keep "first", "1st", "second", ...).

In `looks_like_reference`, replace

    if re.search(r"\b(?:number\s+)?(\d+)(?:st|nd|rd|th)?\b", clean):
        if len(words) <= 5:
            return True

with

    if re.search(r"\b(?:number\s+)?(\d+)(?:st|nd|rd|th)?\b", clean):
        if len(words) <= 5 and (word_set & {"open", "show", "play", "run", "launch",
                                            "number", "pick", "choose", "select"}):
            return True

In `resolve_reference`, change `if num_match and len(words) <= 6:` to

    if num_match and len(words) <= 6 and (word_set & {"open", "show", "play", "run", "launch",
                                                       "number", "pick", "choose", "select"}):

## 3. main_modules/startup/voice_loop.py  (three real voice bugs)

(a) Valid answers were thrown away. "yes", "no" and "bye" are in the hallucination list, so
answering "close all chrome windows?" with "yes" never reached the dialogue manager. Replace

    if text_lower in _hallucinations or len(text_lower) < 2:
        continue

with

    from brain_modules.dialogue_manager import has_pending as _has_pending
    if (text_lower in _hallucinations and not _has_pending()) or len(text_lower) < 2:
        continue

(b) Control words matched ANYWHERE in a sentence. "how do I stop a process" paused Seven,
"what is seven times eight" was swallowed as a wake word, and "how do I shut down the
server" killed Seven. Add next to `_word_match`:

    def _control_match(text, phrases, max_words=4):
        return len(text.split()) <= max_words and _word_match(text, phrases)

then use `_control_match` instead of `_word_match` for KILL_WORDS, WAKE_WORDS and
PAUSE_WORDS, and change the wake block to

    if not is_active and _control_match(text_lower, WAKE_WORDS):
        is_active = True
        ctx.mouth.speak("Listening.")
        app_ui.update_status("RESUMED", "#00ff00")
        if _silence_watcher:
            _silence_watcher.set_paused(False)
        continue

(c) The resume path passed a streaming tuple to the speaker. Change

    response = ctx.brain.think(resume_prompt, speaker_id="default")

to

    response = ctx.brain.think(resume_prompt, speaker_id="default", stream_mode="text")

## 4. frontend/src/pages/Console.jsx  (typing dots only until the first token)

Replace `{sending && <TypingIndicator />}` with

    {sending && messages[messages.length - 1]?.role === 'user' && <TypingIndicator />}

## 5. .gitignore

    config.json.bak
    data/
    seven_data/
    *.db
    trigger_daemon_output.txt
    daemon.out

## 6. Remove the personal data that already shipped

The new config.json is clean, but the old one is in git history. Rewrite history, then
force-push:

    pip install git-filter-repo
    git filter-repo --path config.json --invert-paths
    git add config.json && git commit -m "chore(config): ship clean default config"

Anyone who already installed an earlier build has the developer's email and name in their
%APPDATA%\SEVEN\config.json. They can set Settings > Account, or you can ship a one-time
reset of identity.user_name and email.
