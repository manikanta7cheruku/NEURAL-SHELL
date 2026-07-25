"""
test_baseline.py
Seven production baseline test suite.
Run before any refactor. All tests must pass before deployment.

Usage:
    python test_baseline.py              - run all tests
    python test_baseline.py --fast       - skip slow LLM tests
    python test_baseline.py --section chat - run only chat tests
"""

import requests
import sys
import io
import time
import json
import os
import argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

parser = argparse.ArgumentParser()
parser.add_argument('--fast',    action='store_true', help='Skip slow LLM tests')
parser.add_argument('--section', type=str,            help='Run only this section')
args, _ = parser.parse_known_args()

BASE  = "http://127.0.0.1:7777/api"
PANEL = "http://127.0.0.1:7778"

results   = []
_cleanups = []  # functions to call at end to clean up test data


def test(name, fn, section=None):
    if args.section and section and args.section.lower() != section.lower():
        return
    try:
        result = fn()
        ok = result is True or (isinstance(result, dict) and result.get("ok", False))
        status = "PASS" if ok else "FAIL"
        detail = "" if ok else f" -> {result}"
        print(f"  [{status}] {name}{detail}")
        results.append((name, ok, None if ok else str(result)))
    except Exception as e:
        print(f"  [ERROR] {name} -> {type(e).__name__}: {e}")
        results.append((name, False, f"{type(e).__name__}: {e}"))


def section(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")


def cleanup(fn):
    _cleanups.append(fn)


# ============================================================================
# SECTION: HEALTH
# ============================================================================
section("HEALTH CHECK")

def test_api_alive():
    r = requests.get(f"{BASE}/status", timeout=3)
    return {"ok": r.status_code == 200}
test("API responding on port 7777", test_api_alive, "health")

def test_health_endpoint():
    r = requests.get(f"{BASE}/health", timeout=5)
    if r.status_code != 200:
        return {"ok": False, "status": r.status_code}
    data = r.json()
    required = ["healthy", "elapsed_ms", "checks"]
    return {"ok": all(k in data for k in required), "data": data}
test("Health endpoint returns structured report", test_health_endpoint, "health")

def test_health_speed():
    r = requests.get(f"{BASE}/health", timeout=5)
    if r.status_code != 200:
        return {"ok": False}
    ms = r.json().get("elapsed_ms", 9999)
    return {"ok": ms < 500, "elapsed_ms": ms}
test("Health endpoint responds in under 500ms", test_health_speed, "health")

def test_health_memory_check():
    r = requests.get(f"{BASE}/health", timeout=5)
    if r.status_code != 200:
        return {"ok": False}
    memory = r.json().get("checks", {}).get("memory_db", {})
    return {"ok": "ok" in memory}
test("Health check includes memory_db status", test_health_memory_check, "health")

def test_health_ollama_check():
    r = requests.get(f"{BASE}/health", timeout=5)
    if r.status_code != 200:
        return {"ok": False}
    ollama = r.json().get("checks", {}).get("ollama", {})
    return {"ok": "ok" in ollama}
test("Health check includes ollama status", test_health_ollama_check, "health")

def test_panel_alive():
    try:
        r = requests.get(f"{PANEL}/panel/health", timeout=2)
        return {"ok": r.status_code == 200}
    except Exception:
        return {"ok": True, "note": "panel not running (acceptable)"}
test("Panel server port 7778", test_panel_alive, "health")


# ============================================================================
# SECTION: TASKS
# ============================================================================
section("TASK SYSTEM")

_test_task_id = None

def test_create_task():
    global _test_task_id
    r = requests.post(f"{BASE}/tasks", json={
        "text":        "BASELINE_TEST_TASK_DO_NOT_DELETE",
        "priority":    "high",
        "description": "Created by test_baseline.py",
        "subtasks":    [
            {"id": "st_1", "text": "Subtask one",   "completed": False},
            {"id": "st_2", "text": "Subtask two",   "completed": True},
        ]
    }, timeout=5)
    if r.status_code == 200:
        data = r.json()
        _test_task_id = data.get("task", {}).get("id")
        cleanup(lambda: requests.delete(f"{BASE}/tasks/{_test_task_id}") if _test_task_id else None)
        return {"ok": bool(_test_task_id), "id": _test_task_id}
    return {"ok": False, "status": r.status_code, "body": r.text[:100]}
test("Create task with subtasks", test_create_task, "tasks")

def test_task_has_subtasks():
    if not _test_task_id:
        return {"ok": False, "reason": "no task created"}
    r = requests.get(f"{BASE}/tasks", timeout=5)
    tasks = r.json()
    found = next((t for t in tasks if t["id"] == _test_task_id), None)
    if not found:
        return {"ok": False, "reason": "task not found in list"}
    return {"ok": len(found.get("subtasks", [])) == 2, "subtasks": found.get("subtasks")}
test("Created task has subtasks persisted", test_task_has_subtasks, "tasks")

def test_update_task():
    if not _test_task_id:
        return {"ok": False, "reason": "no task"}
    r = requests.put(f"{BASE}/tasks/{_test_task_id}", json={
        "description": "Updated by baseline test",
        "priority":    "low",
    }, timeout=5)
    if r.status_code != 200:
        return {"ok": False}
    updated = r.json().get("task", {})
    return {"ok": updated.get("priority") == "low"}
test("Update task priority and description", test_update_task, "tasks")

def test_task_stats():
    r = requests.get(f"{BASE}/tasks/stats", timeout=5)
    if r.status_code != 200:
        return {"ok": False}
    data = r.json()
    required = ["total", "pending", "completed", "due_today", "overdue"]
    return {"ok": all(k in data for k in required)}
test("Task stats has all required fields", test_task_stats, "tasks")

def test_complete_task():
    if not _test_task_id:
        return {"ok": False}
    r = requests.put(f"{BASE}/tasks/{_test_task_id}", json={"completed": True}, timeout=5)
    if r.status_code != 200:
        return {"ok": False}
    updated = r.json().get("task", {})
    return {"ok": updated.get("completed") is True}
test("Complete task sets completed=true", test_complete_task, "tasks")

def test_list_tasks():
    r = requests.get(f"{BASE}/tasks", timeout=5)
    return {"ok": r.status_code == 200 and isinstance(r.json(), list)}
test("List tasks returns array", test_list_tasks, "tasks")

def test_tasks_today():
    r = requests.get(f"{BASE}/tasks/today", timeout=5)
    return {"ok": r.status_code == 200 and isinstance(r.json(), list)}
test("Today tasks endpoint", test_tasks_today, "tasks")

def test_tasks_overdue():
    r = requests.get(f"{BASE}/tasks/overdue", timeout=5)
    return {"ok": r.status_code == 200 and isinstance(r.json(), list)}
test("Overdue tasks endpoint", test_tasks_overdue, "tasks")

def test_delete_task():
    if not _test_task_id:
        return {"ok": True, "note": "no task to delete"}
    r = requests.delete(f"{BASE}/tasks/{_test_task_id}", timeout=5)
    return {"ok": r.status_code == 200}
test("Delete task", test_delete_task, "tasks")

def test_delete_nonexistent_task():
    r = requests.delete(f"{BASE}/tasks/999999", timeout=5)
    return {"ok": r.status_code == 404}
test("Delete nonexistent task returns 404", test_delete_nonexistent_task, "tasks")


# ============================================================================
# SECTION: SCHEDULES
# ============================================================================
section("SCHEDULE SYSTEM")

_test_sched_id = None

def test_list_schedules():
    r = requests.get(f"{BASE}/schedules", timeout=5)
    return {"ok": r.status_code == 200 and isinstance(r.json(), list)}
test("List schedules returns array", test_list_schedules, "schedules")

def test_create_schedule():
    global _test_sched_id
    before = {s["id"] for s in requests.get(f"{BASE}/schedules").json()}
    r = requests.post(f"{BASE}/schedules", json={
        "type":    "reminder",
        "message": "BASELINE_TEST_SCHEDULE",
        "time":    "tomorrow 9pm",
    }, timeout=10)
    if r.status_code != 200:
        return {"ok": False, "status": r.status_code, "body": r.text[:150]}
    after = requests.get(f"{BASE}/schedules").json()
    new = [s for s in after if s["id"] not in before]
    if new:
        _test_sched_id = new[0]["id"]
        cleanup(lambda: requests.delete(f"{BASE}/schedules/{_test_sched_id}") if _test_sched_id else None)
        return {"ok": True, "id": _test_sched_id}
    return {"ok": False, "reason": "schedule not found after create"}
test("Create schedule", test_create_schedule, "schedules")

def test_delete_schedule():
    if not _test_sched_id:
        return {"ok": True, "note": "no schedule to delete"}
    r = requests.delete(f"{BASE}/schedules/{_test_sched_id}", timeout=5)
    return {"ok": r.status_code == 200}
test("Delete schedule", test_delete_schedule, "schedules")


# ============================================================================
# SECTION: TRIGGERS
# ============================================================================
section("TRIGGER SYSTEM")

_test_trigger_id = None

def test_list_triggers():
    r = requests.get(f"{BASE}/triggers", timeout=5)
    return {"ok": r.status_code == 200 and isinstance(r.json(), list)}
test("List triggers returns array", test_list_triggers, "triggers")

def test_trigger_stats():
    r = requests.get(f"{BASE}/triggers/stats", timeout=5)
    if r.status_code != 200:
        return {"ok": False}
    data = r.json()
    required = ["total", "enabled", "hotkey", "voice", "audio"]
    return {"ok": all(k in data for k in required)}
test("Trigger stats has all fields", test_trigger_stats, "triggers")

def test_create_trigger():
    global _test_trigger_id
    r = requests.post(f"{BASE}/triggers", json={
        "name":        "BASELINE_TEST_TRIGGER",
        "action_type": "open_url",
        "action_data": {"url": "https://example.com"},
        "hotkey":      "ctrl+shift+9",
        "enabled":     True,
        "silent":      True,
    }, timeout=5)
    if r.status_code == 200:
        _test_trigger_id = r.json().get("trigger", {}).get("id")
        cleanup(lambda: requests.delete(f"{BASE}/triggers/{_test_trigger_id}") if _test_trigger_id else None)
        return {"ok": bool(_test_trigger_id), "id": _test_trigger_id}
    return {"ok": False, "status": r.status_code, "body": r.text[:150]}
test("Create trigger", test_create_trigger, "triggers")

def test_trigger_conflict_hotkey():
    if not _test_trigger_id:
        return {"ok": True, "note": "no trigger to conflict with"}
    r = requests.post(f"{BASE}/triggers", json={
        "name":        "BASELINE_CONFLICT_TRIGGER",
        "action_type": "open_url",
        "action_data": {"url": "https://example.com"},
        "hotkey":      "ctrl+shift+9",
        "enabled":     True,
        "silent":      True,
    }, timeout=5)
    return {"ok": r.status_code == 409, "status": r.status_code}
test("Duplicate hotkey returns 409 conflict", test_trigger_conflict_hotkey, "triggers")

def test_update_trigger():
    if not _test_trigger_id:
        return {"ok": False, "reason": "no trigger"}
    r = requests.put(f"{BASE}/triggers/{_test_trigger_id}", json={"enabled": False}, timeout=5)
    if r.status_code != 200:
        return {"ok": False}
    updated = r.json().get("trigger", {})
    return {"ok": updated.get("enabled") is False}
test("Disable trigger via update", test_update_trigger, "triggers")

def test_delete_trigger():
    if not _test_trigger_id:
        return {"ok": True, "note": "no trigger to delete"}
    r = requests.delete(f"{BASE}/triggers/{_test_trigger_id}", timeout=5)
    return {"ok": r.status_code == 200}
test("Delete trigger", test_delete_trigger, "triggers")


# ============================================================================
# SECTION: MEMORY
# ============================================================================
section("MEMORY SYSTEM")

def test_memory_stats():
    r = requests.get(f"{BASE}/memory/stats", timeout=5)
    if r.status_code != 200:
        return {"ok": False, "status": r.status_code}
    data = r.json()
    required = ["total_conversations", "total_facts", "storage_mb"]
    return {"ok": all(k in data for k in required), "stats": data}
test("Memory stats has all fields", test_memory_stats, "memory")

def test_memory_stats_nonzero():
    r = requests.get(f"{BASE}/memory/stats", timeout=5)
    if r.status_code != 200:
        return {"ok": False}
    data = r.json()
    convos = data.get("total_conversations", 0)
    return {"ok": convos > 0, "conversations": convos}
test("Memory has existing conversations", test_memory_stats_nonzero, "memory")

def test_conversations_endpoint():
    r = requests.get(f"{BASE}/memory/conversations?limit=5", timeout=5)
    if r.status_code != 200:
        return {"ok": False, "status": r.status_code, "body": r.text[:200]}
    data = r.json()
    return {
        "ok": "conversations" in data and "total" in data,
        "total": data.get("total"),
        "returned": len(data.get("conversations", [])),
    }
test("Conversations endpoint returns data", test_conversations_endpoint, "memory")

def test_conversation_fields():
    r = requests.get(f"{BASE}/memory/conversations?limit=1", timeout=5)
    if r.status_code != 200:
        return {"ok": False}
    convos = r.json().get("conversations", [])
    if not convos:
        return {"ok": True, "note": "no conversations to check fields"}
    c = convos[0]
    required = ["id", "user_input", "seven_response", "timestamp", "source"]
    missing = [k for k in required if k not in c]
    return {"ok": len(missing) == 0, "missing_fields": missing}
test("Conversation records have all required fields", test_conversation_fields, "memory")

def test_facts_endpoint():
    r = requests.get(f"{BASE}/memory/facts", timeout=5)
    if r.status_code != 200:
        return {"ok": False, "status": r.status_code}
    return {"ok": isinstance(r.json(), list), "count": len(r.json())}
test("Facts endpoint returns array", test_facts_endpoint, "memory")


# ============================================================================
# SECTION: CHAT (slow - uses LLM)
# ============================================================================
section("CHAT AND BRAIN")

if not args.fast:
    def test_chat_greeting():
        r = requests.post(f"{BASE}/chat", json={
            "text": "hello", "speaker_id": "default"
        }, timeout=30)
        if r.status_code != 200:
            return {"ok": False, "status": r.status_code}
        data = r.json()
        return {"ok": bool(data.get("response")) and len(data["response"]) > 2}
    test("Chat greeting returns response", test_chat_greeting, "chat")

    def test_chat_capability():
        r = requests.post(f"{BASE}/chat", json={
            "text": "what can you do", "speaker_id": "default"
        }, timeout=60)
        if r.status_code != 200:
            return {"ok": False, "status": r.status_code}
        return {"ok": len(r.json().get("response", "")) > 5}
    test("Chat capability question hits LLM", test_chat_capability, "chat")

    def test_chat_task_create():
        unique = f"baselinetest_{int(time.time())}"
        before = {t["text"] for t in requests.get(f"{BASE}/tasks").json()}
        r = requests.post(f"{BASE}/chat", json={
            "text": f"add task {unique}", "speaker_id": "default"
        }, timeout=30)
        if r.status_code != 200:
            return {"ok": False}
        time.sleep(0.5)
        after = requests.get(f"{BASE}/tasks").json()
        new = [t for t in after if t["text"] not in before]
        for t in new:
            if unique in t.get("text", ""):
                cleanup(lambda tid=t["id"]: requests.delete(f"{BASE}/tasks/{tid}"))
        return {"ok": len(new) > 0, "new_tasks": len(new)}
    test("Chat creates task via TASK tag", test_chat_task_create, "chat")

    def test_chat_empty_input():
        r = requests.post(f"{BASE}/chat", json={
            "text": "", "speaker_id": "default"
        }, timeout=10)
        return {"ok": r.status_code == 400}
    test("Chat rejects empty input with 400", test_chat_empty_input, "chat")

else:
    print("  [SKIP] LLM tests skipped (--fast mode)")


# ============================================================================
# SECTION: SYSTEM INFO
# ============================================================================
section("SYSTEM INFO")

def test_hardware():
    r = requests.get(f"{BASE}/hardware", timeout=5)
    return {"ok": r.status_code == 200}
test("Hardware endpoint", test_hardware, "system")

def test_status():
    r = requests.get(f"{BASE}/status", timeout=5)
    if r.status_code != 200:
        return {"ok": False}
    data = r.json()
    return {"ok": "model" in data or "listening" in data}
test("Status endpoint has model or listening field", test_status, "system")

def test_config():
    r = requests.get(f"{BASE}/config", timeout=5)
    return {"ok": r.status_code == 200}
test("Config endpoint", test_config, "system")

def test_license():
    r = requests.get(f"{BASE}/license/status", timeout=5)
    return {"ok": r.status_code == 200}
test("License status endpoint", test_license, "system")

def test_usage():
    r = requests.get(f"{BASE}/usage/stats", timeout=5)
    return {"ok": r.status_code == 200}
test("Usage stats endpoint", test_usage, "system")


# ============================================================================
# CLEANUP
# ============================================================================
section("CLEANUP")

for fn in _cleanups:
    try:
        fn()
    except Exception:
        pass
print("  Test data cleaned up")


# ============================================================================
# SUMMARY
# ============================================================================
section("SUMMARY")

passed = sum(1 for _, p, _ in results if p)
failed = sum(1 for _, p, _ in results if not p)
total  = len(results)

print(f"\n  Total: {total}  |  Passed: {passed}  |  Failed: {failed}\n")

if failed > 0:
    print("  FAILURES:")
    for name, ok, err in results:
        if not ok:
            print(f"    X {name}")
            if err:
                print(f"      -> {err}")
    print()

sys.exit(0 if failed == 0 else 1)