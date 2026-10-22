"""
scripts/run_evals.py

Runs evals/golden_conversations.json against a RUNNING Seven (real model, real
latency). Unlike the unit tests, this measures what a person would experience.

    python scripts/run_evals.py [--url http://127.0.0.1:7777] [--include-nondeterministic]

Checks use contains/forbids only, because real model wording varies. Steps
marked "web" need a controlled network and are skipped here (the unit suite
covers them with a fake provider). Prints pass/fail per step and median first-token time.
"""
import argparse
import json
import os
import statistics
import sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ask(url, text, conv):
    first, parts = None, []
    import time
    t0 = time.time()
    with requests.post(f"{url}/api/chat", json={"text": text, "stream": True, "conversation_id": conv},
                       stream=True, timeout=180) as r:
        for line in r.iter_lines():
            if not line.startswith(b"data:"):
                continue
            body = line[5:].strip()
            if body == b"[DONE]":
                break
            try:
                ev = json.loads(body)
            except ValueError:
                continue
            if ev.get("conversation_id"):
                conv = ev["conversation_id"]
            if ev.get("token"):
                first = first if first is not None else int((time.time() - t0) * 1000)
                parts.append(ev["token"])
    return "".join(parts).strip(), first, conv


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:7777")
    ap.add_argument("--include-nondeterministic", action="store_true")
    args = ap.parse_args()
    goldens = json.load(open(os.path.join(ROOT, "evals", "golden_conversations.json"), encoding="utf-8"))
    failures, firsts = 0, []
    for g in goldens:
        if g.get("web"):
            print(f"SKIP  {g['name']} (needs a controlled network)")
            continue
        conv = requests.post(f"{args.url}/api/conversations", json={}, timeout=10).json()["conversation_id"]
        print(f"\n== {g['name']}")
        for step in g["steps"]:
            if step.get("new_chat"):
                conv = requests.post(f"{args.url}/api/conversations", json={}, timeout=10).json()["conversation_id"]
            reply, first, conv = ask(args.url, step["say"], conv)
            if first:
                firsts.append(first)
            low, problems = reply.lower(), []
            if step.get("deterministic", True) or args.include_nondeterministic:
                problems += [f"missing {s!r}" for s in step.get("expect_all", []) if s.lower() not in low]
                if step.get("expect_any") and not any(s.lower() in low for s in step["expect_any"]):
                    problems.append(f"none of {step['expect_any']}")
                problems += [f"contains {s!r}" for s in step.get("forbid", []) if s.lower() in low]
            failures += bool(problems)
            print(f"  {'FAIL' if problems else 'ok  '} {step['say'][:60]!r} -> {reply[:80]!r} {problems or ''}")
    if firsts:
        print(f"\nfirst token: median {int(statistics.median(firsts))} ms, max {max(firsts)} ms over {len(firsts)} replies")
    print(f"{failures} failing step(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
