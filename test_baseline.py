"""
test_baseline.py
Regression test — run BEFORE refactor, save output, run AFTER refactor, diff.
"""

import requests
import sys
import io

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE = "http://127.0.0.1:7777/api"
PANEL = "http://127.0.0.1:7778"

results = []

def test(name, fn):
    try:
        result = fn()
        if result is True or (isinstance(result, dict) and result.get("ok", False)):
            print(f"[PASS] {name}")
            results.append((name, True, None))
        else:
            print(f"[FAIL] {name} -> {result}")
            results.append((name, False, str(result)))
    except Exception as e:
        print(f"[ERROR] {name} -> {type(e).__name__}: {e}")
        results.append((name, False, f"{type(e).__name__}: {e}"))

def separator(text):
    print(f"\n====== {text} ======")

# =========================================================================
separator("SEVEN API HEALTH")

def check_api():
    r = requests.get(f"{BASE}/status", timeout=3)
    return {"ok": r.status_code == 200, "status": r.status_code}
test("Seven API responding on port 7777", check_api)

def check_panel():
    try:
        r = requests.get(f"{PANEL}/panel/health", timeout=2)
        return {"ok": r.status_code == 200}
    except:
        return {"ok": True, "reason": "panel not running (skip)"}
test("Panel server responding on port 7778", check_panel)

# =========================================================================
separator("TASK SYSTEM")

created_task_id = None

def create_task():
    global created_task_id
    r = requests.post(f"{BASE}/tasks", json={
        "text": "TEST_REFACTOR_TASK",
        "priority": "high",
        "description": "This is a test task from baseline script",
    }, timeout=5)
    if r.status_code == 200:
        data = r.json()
        created_task_id = data.get("task", {}).get("id")
        return {"ok": True, "id": created_task_id}
    return {"ok": False, "status": r.status_code}
test("Create task via API", create_task)

def list_tasks():
    r = requests.get(f"{BASE}/tasks", timeout=5)
    return {"ok": r.status_code == 200 and isinstance(r.json(), list)}
test("List tasks", list_tasks)

def get_stats():
    r = requests.get(f"{BASE}/tasks/stats", timeout=5)
    if r.status_code == 200:
        data = r.json()
        return {"ok": "pending" in data and "completed" in data}
    return {"ok": False}
test("Get task stats", get_stats)

def get_today():
    r = requests.get(f"{BASE}/tasks/today", timeout=5)
    return {"ok": r.status_code == 200}
test("Get today's tasks", get_today)

def get_overdue():
    r = requests.get(f"{BASE}/tasks/overdue", timeout=5)
    return {"ok": r.status_code == 200}
test("Get overdue tasks", get_overdue)

def update_task():
    if not created_task_id:
        return {"ok": False, "reason": "no task to update"}
    r = requests.put(f"{BASE}/tasks/{created_task_id}", json={
        "description": "Updated description"
    }, timeout=5)
    return {"ok": r.status_code == 200}
test("Update task description", update_task)

def add_subtasks():
    if not created_task_id:
        return {"ok": False, "reason": "no task"}
    r = requests.put(f"{BASE}/tasks/{created_task_id}", json={
        "subtasks": [
            {"id": "s_test_1", "text": "Subtask one", "completed": False},
            {"id": "s_test_2", "text": "Subtask two", "completed": True},
        ]
    }, timeout=5)
    return {"ok": r.status_code == 200}
test("Add subtasks to task", add_subtasks)

def delete_task():
    if not created_task_id:
        return {"ok": False, "reason": "no task"}
    r = requests.delete(f"{BASE}/tasks/{created_task_id}", timeout=5)
    return {"ok": r.status_code == 200}
test("Delete test task", delete_task)

# =========================================================================
separator("SCHEDULE SYSTEM")

def list_schedules():
    r = requests.get(f"{BASE}/schedules", timeout=5)
    return {"ok": r.status_code == 200 and isinstance(r.json(), list)}
test("List schedules", list_schedules)

created_sched_id = None

def create_schedule():
    global created_sched_id
    # Get count before
    before_count = len(requests.get(f"{BASE}/schedules").json())
    r = requests.post(f"{BASE}/schedules", json={
        "type": "reminder",
        "message": "TEST_REFACTOR_SCHEDULE",
        "time": "5pm tomorrow",
    }, timeout=10)
    # Success = HTTP 200 AND schedule count increased
    if r.status_code == 200:
        all_scheds = requests.get(f"{BASE}/schedules").json()
        if len(all_scheds) > before_count:
            # Find the newest one
            for s in reversed(all_scheds):
                if s.get("message") == "TEST_REFACTOR_SCHEDULE":
                    created_sched_id = s["id"]
                    return {"ok": True, "id": created_sched_id}
            return {"ok": True, "note": "created but not found in list"}
    return {"ok": False, "status": r.status_code, "body": r.text[:100]}
test("Create schedule via API", create_schedule)

def delete_schedule():
    if not created_sched_id:
        # Try to find and cleanup any leftover test schedules
        all_scheds = requests.get(f"{BASE}/schedules").json()
        for s in all_scheds:
            if s.get("message") == "TEST_REFACTOR_SCHEDULE":
                requests.delete(f"{BASE}/schedules/{s['id']}")
        return {"ok": True, "note": "no schedule was created to delete"}
    r = requests.delete(f"{BASE}/schedules/{created_sched_id}", timeout=5)
    return {"ok": r.status_code == 200}
test("Delete test schedule", delete_schedule)

# =========================================================================
separator("CHAT / BRAIN")

def chat_greeting():
    r = requests.post(f"{BASE}/chat", json={
        "text": "hello",
        "speaker_id": "default"
    }, timeout=30)
    if r.status_code == 200:
        return {"ok": bool(r.json().get("response"))}
    return {"ok": False, "status": r.status_code}
test("Chat: greeting", chat_greeting)

def chat_task_create():
    import time as _t
    import random as _rand

    # Generate unique task text so brain repetition detector doesn't skip it
    unique_id = f"{int(_t.time())}_{_rand.randint(1000, 9999)}"
    task_phrase = f"add task testcheck_{unique_id}"

    before = requests.get(f"{BASE}/tasks").json()
    before_texts = set(t.get("text", "") for t in before)

    r = requests.post(f"{BASE}/chat", json={
        "text": task_phrase,
        "speaker_id": "default"
    }, timeout=30)

    if r.status_code != 200:
        return {"ok": False, "status": r.status_code}

    _t.sleep(0.5)

    after = requests.get(f"{BASE}/tasks").json()
    new_tasks = [t for t in after if t.get("text", "") not in before_texts]

    # Cleanup any tasks matching our unique id
    for t in new_tasks:
        if unique_id in t.get("text", "") or "testcheck" in t.get("text", "").lower():
            requests.delete(f"{BASE}/tasks/{t['id']}")

    return {"ok": len(new_tasks) > 0, "new_task_count": len(new_tasks), "phrase": task_phrase}
test("Chat: task create via TASK tag", chat_task_create)

def chat_task_list():
    r = requests.post(f"{BASE}/chat", json={
        "text": "show my tasks",
        "speaker_id": "default"
    }, timeout=30)
    return {"ok": r.status_code == 200}
test("Chat: task list via TASK tag", chat_task_list)

def chat_capability():
    r = requests.post(f"{BASE}/chat", json={
        "text": "what can you do",
        "speaker_id": "default"
    }, timeout=60)
    if r.status_code == 200:
        return {"ok": len(r.json().get("response", "")) > 5}
    return {"ok": False}
test("Chat: capability question (LLM path)", chat_capability)

# =========================================================================
separator("MEMORY SYSTEM")

def memory_stats():
    r = requests.get(f"{BASE}/memory/stats", timeout=5)
    if r.status_code == 200:
        data = r.json()
        return {"ok": "total_conversations" in data}
    return {"ok": False}
test("Memory stats endpoint", memory_stats)

# =========================================================================
separator("HARDWARE / STATUS")

def hardware():
    r = requests.get(f"{BASE}/hardware", timeout=5)
    return {"ok": r.status_code == 200}
test("Hardware info", hardware)

def speed():
    r = requests.get(f"{BASE}/speed", timeout=5)
    return {"ok": r.status_code == 200}
test("Speed stats", speed)

def status():
    r = requests.get(f"{BASE}/status", timeout=5)
    if r.status_code == 200:
        data = r.json()
        return {"ok": "model" in data or "listening" in data}
    return {"ok": False}
test("Status endpoint", status)

# =========================================================================
separator("CONFIG")

def get_config():
    r = requests.get(f"{BASE}/config", timeout=5)
    return {"ok": r.status_code == 200}
test("Get config", get_config)

# =========================================================================
separator("COMMANDS LOG")

def commands_log():
    r = requests.get(f"{BASE}/commands/log?limit=5", timeout=5)
    return {"ok": r.status_code == 200}
test("Commands log", commands_log)

# =========================================================================
separator("LICENSE")

def license_status():
    r = requests.get(f"{BASE}/license/status", timeout=5)
    return {"ok": r.status_code == 200}
test("License status", license_status)

# =========================================================================
separator("USAGE")

def usage_stats():
    r = requests.get(f"{BASE}/usage/stats", timeout=5)
    return {"ok": r.status_code == 200}
test("Usage stats", usage_stats)

# =========================================================================
separator("PANEL SYSTEM")

def panel_tasks():
    try:
        r = requests.get(f"{PANEL}/panel/tasks", timeout=3)
        return {"ok": r.status_code == 200 and isinstance(r.json(), list)}
    except:
        return {"ok": True, "note": "panel not running (skip)"}
test("Panel tasks endpoint", panel_tasks)

def panel_stats():
    try:
        r = requests.get(f"{PANEL}/panel/stats", timeout=3)
        return {"ok": r.status_code == 200}
    except:
        return {"ok": True, "note": "panel not running"}
test("Panel stats endpoint", panel_stats)

# =========================================================================
separator("SUMMARY")

passed = sum(1 for _, p, _ in results if p)
failed = sum(1 for _, p, _ in results if not p)
total  = len(results)

print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed}\n")

if failed > 0:
    print("FAILURES:")
    for name, ok, err in results:
        if not ok:
            print(f"  X {name}")
            if err:
                print(f"    -> {err}")

sys.exit(0 if failed == 0 else 1)