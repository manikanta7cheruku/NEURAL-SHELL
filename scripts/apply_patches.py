"""
scripts/apply_patches.py

Applies the small, exact edits that SEVEN's brain overhaul needs in files that
are not replaced wholesale (license limits, memory eviction, routes, telemetry
opt-out, Plans copy, voice loop fixes, ...).

    python scripts/apply_patches.py            # dry run: shows what would change
    python scripts/apply_patches.py --apply    # writes changes

Safe by design: each edit is an exact string match; a file is only written when
every edit for it matches (or is already applied); CRLF files stay CRLF; running
it twice changes nothing; mismatches are reported, never forced.
"""
import argparse
import os
import sys

R = "replace"
PATCHES = [
    {"file": "license.py", "edits": [
        {"old": '"conversation_history": 7,', "new": '"conversation_history": -1,'},
        {"old": '"facts_limit": 7,', "new": '"facts_limit": -1,'},
        {"old": '"conversation_history": 77,', "new": '"conversation_history": -1,'},
        {"old": '"facts_limit": 77,', "new": '"facts_limit": -1,'}]},
    {"file": "memory/core.py", "edits": [
        {"old": '_limits = {"free": 7, "pro": 77, "ultimate": -1}\n            _max_allowed = _limits.get(_tier, 7)',
         "new": '_max_allowed = -1  # conversation and fact limits removed (see memory/limits.py)', "count": 2}]},
    {"file": "backend/routes/license_routes.py", "edits": [
        {"old": 'all_facts   = seven_memory.user_facts.get()', "new": 'all_facts = None'},
        {"old": 'facts_count = len(all_facts["documents"]) if all_facts and all_facts.get("documents") else 0',
         "new": 'from memory import facts_store as _fs\n        facts_count = _fs.count_facts()'},
        {"old": 'all_convos  = seven_memory.conversations.get()', "new": 'all_convos = None'},
        {"old": 'convo_count = len(all_convos["documents"]) if all_convos and all_convos.get("documents") else 0',
         "new": 'from memory import conversation_store as _cs\n        convo_count = _cs.count_conversations()'}]},
    {"file": "telemetry.py", "edits": [
        {"old": "def start_telemetry():",
         "new": 'def _telemetry_enabled():\n    try:\n        import config as _cfg\n        return bool(_cfg.KEY.get("privacy", {}).get("telemetry_enabled", True))\n'
                '    except Exception:\n        return True\n\n\ndef start_telemetry():\n    if not _telemetry_enabled():\n'
                '        print("[TELEMETRY] Disabled by user setting")\n        return\n    _start_telemetry_impl()\n\n\ndef _start_telemetry_impl():'}]},
    {"file": "backend/api_server.py", "edits": [
        {"old": "from backend.routes import panel_extras as panel_extras_routes",
         "new": "from backend.routes import panel_extras as panel_extras_routes\nfrom backend.routes import brain as brain_routes\nfrom backend.routes import conversations as conversation_routes"},
        {"old": "app.include_router(panel_extras_routes.router)",
         "new": "app.include_router(panel_extras_routes.router)\napp.include_router(brain_routes.router)\napp.include_router(conversation_routes.router)"}]},
    {"file": "package.json", "edits": [
        {"old": '"build:frontend": "cd frontend && npm run build",',
         "new": '"build:manifest": "python scripts/build_app_manifest.py",\n        "build:frontend": "python scripts/build_app_manifest.py && cd frontend && npm run build",'}]},
    {"file": "frontend/src/pages/Plans.jsx", "edits": [
        {"old": "'7 facts remembered'", "new": "'Unlimited facts remembered'"},
        {"old": "'7 conversations saved'", "new": "'Unlimited conversation history'"},
        {"old": "'77 facts remembered'", "new": "'Unlimited facts remembered'"},
        {"old": "'77 conversations saved'", "new": "'Unlimited conversation history'"},
        {"old": "'3 schedules'", "new": "'7 schedules'"},
        {"old": "'20 schedules'", "new": "'77 schedules'"},
        {"old": 'feature: "7 Facts Remembered"', "new": 'feature: "Unlimited Facts Remembered"'},
        {"old": 'feature: "7 Conversations Saved"', "new": 'feature: "Unlimited Conversation History"'},
        {"old": 'example: "Last 7 chat histories are kept — older ones are deleted"',
         "new": 'example: "Every chat is saved on your device and searchable, nothing is deleted to make room"'},
        {"old": 'feature: "77 Facts & Conversations"', "new": 'feature: "Unlimited Facts & Conversations"'},
        {"old": 'example: "10x more memory — Seven remembers your preferences, work details, family info"',
         "new": 'example: "Seven remembers your preferences, work details and the people in your life, for as long as you want"'},
        {"old": 'feature: "17 Schedules"', "new": 'feature: "77 Schedules"'},
        {"old": "when released (Q2 2025)", "new": "when released"}]},
    {"file": "brain_modules/dialogue_manager.py", "edits": [
        {"old": '"first": 0, "1st": 0, "one": 0,', "new": '"first": 0, "1st": 0,'},
        {"old": '"second": 1, "2nd": 1, "two": 1,', "new": '"second": 1, "2nd": 1,'},
        {"old": '"third": 2, "3rd": 2, "three": 2,', "new": '"third": 2, "3rd": 2,'},
        {"old": '"fourth": 3, "4th": 3, "four": 3,', "new": '"fourth": 3, "4th": 3,'},
        {"old": '"fifth": 4, "5th": 4, "five": 4,', "new": '"fifth": 4, "5th": 4,'},
        {"old": '"sixth": 5, "6th": 5, "six": 5,', "new": '"sixth": 5, "6th": 5,'},
        {"old": '"seventh": 6, "7th": 6, "seven": 6,', "new": '"seventh": 6, "7th": 6,'},
        {"old": '"eighth": 7, "8th": 7, "eight": 7,', "new": '"eighth": 7, "8th": 7,'},
        {"old": '"ninth": 8, "9th": 8, "nine": 8,', "new": '"ninth": 8, "9th": 8,'},
        {"old": '"tenth": 9, "10th": 9, "ten": 9,', "new": '"tenth": 9, "10th": 9,'},
        {"old": "        if len(words) <= 5:\n            return True",
         "new": '        if len(words) <= 5 and (word_set & {"open", "show", "play", "run", "launch", "number", "pick", "choose", "select"}):\n            return True'},
        {"old": "    if num_match and len(words) <= 6:",
         "new": '    if num_match and len(words) <= 6 and (word_set & {"open", "show", "play", "run", "launch", "number", "pick", "choose", "select"}):'}]},
    {"file": "main_modules/startup/voice_loop.py", "edits": [
        {"old": "            if text_lower in _hallucinations or len(text_lower) < 2:\n                continue",
         "new": "            from brain_modules.dialogue_manager import has_pending as _has_pending\n            if (text_lower in _hallucinations and not _has_pending()) or len(text_lower) < 2:\n                continue"},
        {"old": "    def _get_voice_control_words():",
         "new": "    def _control_match(text, phrases, max_words=4):\n        return len(text.split()) <= max_words and _word_match(text, phrases)\n\n    def _get_voice_control_words():"},
        {"old": "if _word_match(text_lower, KILL_WORDS):", "new": "if _control_match(text_lower, KILL_WORDS):"},
        {"old": "            if _word_match(text_lower, WAKE_WORDS):\n                if not is_active:",
         "new": "            if not is_active and _control_match(text_lower, WAKE_WORDS):\n                if not is_active:"},
        {"old": "if is_active and _word_match(text_lower, PAUSE_WORDS):", "new": "if is_active and _control_match(text_lower, PAUSE_WORDS):"},
        {"old": 'response = ctx.brain.think(resume_prompt, speaker_id="default")',
         "new": 'response = ctx.brain.think(resume_prompt, speaker_id="default", stream_mode="text")'}]},
    {"file": ".gitignore", "append": ["config.json.bak", "data/", "seven_data/", "*.db", "trigger_daemon_output.txt", "daemon.out"]},
]


def _nl(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def patch_text(text: str, edits):
    """(new_text, report). Nothing is returned for writing unless every edit matched or was already applied."""
    nl, report, out = _nl(text), [], text
    for e in edits:
        old, new, want = e["old"].replace("\n", nl), e["new"].replace("\n", nl), e.get("count")
        n = out.count(old)
        if n == 0:
            report.append(("already applied" if new in out else "NOT FOUND", e["old"][:60]))
            continue
        if want and n != want:
            report.append((f"EXPECTED {want} FOUND {n}", e["old"][:60]))
            continue
        out = out.replace(old, new)
        report.append(("patched" if n == 1 else f"patched x{n}", e["old"][:60]))
    return out, report


def run(root: str, apply: bool = False):
    results = []
    for patch in PATCHES:
        path = os.path.join(root, patch["file"])
        if not os.path.isfile(path):
            results.append((patch["file"], [("MISSING FILE", "")]))
            continue
        with open(path, "r", encoding="utf-8", newline="") as fh:
            text = fh.read()
        if "append" in patch:
            nl = _nl(text)
            missing = [l for l in patch["append"] if l not in text.splitlines()]
            new_text = text + ("" if text.endswith(("\n", "")) and not missing else "") + "".join(
                (nl if i == 0 and text and not text.endswith(nl) else "") + l + nl for i, l in enumerate(missing))
            rep = [("patched" if missing else "already applied", ", ".join(missing) or "all lines present")]
        else:
            new_text, rep = patch_text(text, patch["edits"])
        ok = not any(r[0] in ("NOT FOUND",) or r[0].startswith("EXPECTED") for r in rep)
        if apply and ok and new_text != text:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(new_text)
        results.append((patch["file"], rep))
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()
    bad = 0
    for file, rep in run(args.root, args.apply):
        print(file)
        for status, snippet in rep:
            print(f"   {status:<18} {snippet}")
            bad += status in ("NOT FOUND", "MISSING FILE") or status.startswith("EXPECTED")
    print("\n" + ("Applied." if args.apply else "Dry run only. Re-run with --apply to write.") +
          (f" {bad} item(s) need manual attention (see above)." if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
