# SEVEN — Path to Production Readiness

**Version:** 1.0  
**Last Updated:** September 2026  
**Status:** Advanced Prototype → Professional Product

---

## Executive Summary

Seven is a **private, local-first AI voice assistant for Windows** with strong product differentiation but critical gaps in reliability, security, and user trust before public launch. This document charts a phased path to production readiness across four pillars: **Reliability**, **Security**, **User Experience**, and **Operations**.

### Product Positioning

**Target Users (Phase 1):**
- Privacy-conscious professionals
- Developers and power users
- Local-AI enthusiasts
- Accessibility users
- Enterprise/offline-first teams

**Tagline:**  
> "Your private AI operator for Windows. Runs entirely on your machine. No cloud. No tracking."

**Core Promise:**
- 🔒 Truly private — all processing local, no data sent anywhere
- 🎙️ Voice-first — optimized for hands-free control
- ⚙️ Powerful — system automation, tasks, schedules, memory
- 📴 Offline-capable — works without internet
- 🚀 Fast — instant response, no API latency

---

## Phase 1: Foundation (Weeks 1-4)

### Goal
Make Seven reliable enough for early adopters to trust with daily use.

### 1.1 Reliability: Action Execution Model

**Current state:** Actions (open app, create task, etc.) execute synchronously in the chat request path. No retry, no confirmation, no structured logging.

**Target state:** Safe, observable, reversible actions.

**Implementation:**

```python
# backend/models/action.py
from enum import Enum
from pydantic import BaseModel
from datetime import datetime

class ActionSafety(Enum):
    SAFE = "safe"           # Auto-execute
    SENSITIVE = "sensitive" # Confirm once per type
    DANGEROUS = "dangerous" # Always confirm

class Action(BaseModel):
    id: str
    type: str  # "launch_app", "create_task", "delete_file", etc.
    params: dict
    safety: ActionSafety
    description: str  # Human-readable: "Open Chrome"
    timestamp: datetime
    status: str  # pending, executing, success, failed
    error: str | None = None
    duration_ms: int | None = None

class ActionApproval(BaseModel):
    action_id: str
    user_approved: bool
    approved_at: datetime
    remember: bool  # "Always allow this action type?"
```

**Safety matrix:**

| Action | Safety | Examples |
|--------|--------|----------|
| SAFE | Auto-execute | Open app, create task, set reminder, search files, read memory |
| SENSITIVE | Confirm once | Delete task, clear memory, modify settings, run script |
| DANGEROUS | Always confirm | Delete files, send messages, modify system settings, install software |

**Action router:**

```python
# backend/routes/actions.py
async def execute_action(action: Action, session_user: str) -> ActionResult:
    """Execute action with approval, retry, and audit logging."""
    
    # 1. Log the intent
    log_action_audit(action, "requested", session_user)
    
    # 2. Check approval requirement
    if action.safety == ActionSafety.DANGEROUS:
        return ActionResult(status="pending_approval", action_id=action.id)
    
    # 3. Execute with timeout + retry
    try:
        result = await execute_with_timeout(
            action.type,
            action.params,
            timeout_ms=5000,
            max_retries=2
        )
        log_action_audit(action, "success", session_user, result)
        return ActionResult(status="success", result=result)
    except Exception as e:
        log_action_audit(action, "failed", session_user, str(e))
        return ActionResult(status="failed", error=str(e))
```

**What to do:**
- [ ] Create `backend/models/action.py` with safety enums and schemas
- [ ] Create `backend/routes/actions.py` with execution router
- [ ] Replace inline action execution in chat route with `execute_action()`
- [ ] Add action audit table to SQLite: `CREATE TABLE action_audit (id, type, params, status, error, user_id, timestamp)`
- [ ] Add `/api/actions/pending` endpoint to fetch pending approvals
- [ ] Add `/api/actions/{id}/approve` endpoint for user confirmation
- [ ] Wire approval UI into the React dashboard (modal confirmation)

**Success metric:** 100% of actions logged, 0% of dangerous actions execute without confirmation.

---

### 1.2 Security: Authentication & Permissions

**Current state:** No authentication. All endpoints accessible to any local process.

**Target state:** Per-installation API token, origin validation, permission scopes.

**Implementation:**

```python
# backend/auth/token.py
import secrets
from pathlib import Path

def generate_api_token() -> str:
    """Generate a secure random token on first app launch."""
    return secrets.token_urlsafe(32)  # 43-char token

def load_or_create_token(app_data_dir: Path) -> str:
    """Load existing token or create new one."""
    token_file = app_data_dir / ".seven_token"
    if token_file.exists():
        return token_file.read_text().strip()
    token = generate_api_token()
    token_file.write_text(token)
    token_file.chmod(0o600)  # Owner-only read/write
    return token
```

```python
# backend/middleware/auth.py
from fastapi import HTTPException, Header

async def validate_api_token(authorization: str = Header(None)) -> str:
    """Verify Bearer token matches app's token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API token")
    
    token = authorization.split(" ")[1]
    if token != os.getenv("SEVEN_API_TOKEN"):
        raise HTTPException(status_code=403, detail="Invalid token")
    
    return token
```

**What to do:**
- [ ] Add API token generation on first app launch (store in `~/.seven/config/api_token`)
- [ ] Add `Authorization: Bearer <token>` requirement to all endpoints except `/health`
- [ ] Add `X-Requested-By: SEVEN` header requirement (IPC only)
- [ ] Restrict CORS to Electron window origin only
- [ ] Document token recovery (if lost, user regenerates and re-authorizes app)

**Success metric:** Unauthenticated requests return 401, all mutations require token.

---

### 1.3 User Experience: Onboarding & First Run

**Current state:** User installs, downloads model, launches app. Success is undefined.

**Target state:** Guided 5-minute setup that proves value immediately.

**Onboarding flow:**

1. **Language & mic test** (30s)
   - Select language/accent
   - Microphone level meter
   - Record test phrase "Hello, can you hear me?"
   - Play back recording, confirm clarity

2. **Model selection** (2m)
   - Show available models (Llama 2, Mistral, etc.)
   - Display VRAM/RAM requirements vs. system specs
   - Let user pick or auto-select "medium" (safe default)
   - Begin background download with progress bar, ETA, pause/cancel

3. **First command** (1m)
   - While model downloads, show sample commands
   - "Open my work apps" → launches Chrome, Slack, VS Code
   - "Create a task: call mom at 2pm"
   - "What's the weather?" (if online)
   - Let user pick one to execute

4. **Workspace snapshot** (1m)
   - "I can save your apps so you can restore them later"
   - Show checkbox: "Save my current workspace"
   - Explain workspace restore feature

5. **Done** ✓
   - Show keyboard shortcut (Alt+Shift+T)
   - Offer to open tutorial or settings

**What to do:**
- [ ] Create `frontend/src/pages/Onboarding.jsx` with 5 steps
- [ ] Add Zustand store to track onboarding state (`useOnboarding.js`)
- [ ] Add `/api/onboarding/status`, `/api/onboarding/mic-test`, `/api/onboarding/model-download`
- [ ] Detect first-run via `~/.seven/config/.onboarded` flag
- [ ] Show onboarding modal on app launch if not completed
- [ ] Add sample command templates ("Open work apps", "Create task", "Set reminder")

**Success metric:** First-time users complete onboarding, understand voice input, create 1 task.

---

### 1.4 Observability: Structured Logging & Error Messages

**Current state:** Scattered `print()` statements. Exception tracebacks exposed to users.

**Target state:** Structured JSON logs. User-friendly error messages.

**Implementation:**

```python
# backend/utils/logging.py
import json
from datetime import datetime

class StructuredLogger:
    """Emit JSON-structured logs for debugging and analytics."""
    
    def __init__(self, component: str):
        self.component = component
    
    def info(self, msg: str, **data):
        self._log("info", msg, data)
    
    def error(self, msg: str, error: Exception = None, **data):
        self._log("error", msg, {
            **data,
            "exception": str(error),
            "type": error.__class__.__name__ if error else None
        })
    
    def _log(self, level: str, msg: str, data: dict):
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "component": self.component,
            "message": msg,
            **data
        }
        print(json.dumps(record))  # Stdout for JSON capture

logger = StructuredLogger("core")
```

**Error codes:**

```python
# backend/errors.py
class SevenError(Exception):
    """Base error with user-friendly message."""
    code: str
    message: str
    details: dict = {}
    
    def to_api(self):
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details
        }

class ModelNotReadyError(SevenError):
    code = "MODEL_NOT_READY"
    message = "AI model is still loading. Please wait."

class ActionFailedError(SevenError):
    code = "ACTION_FAILED"
    message = "Unable to complete this action. Please try again."

class MicrophoneError(SevenError):
    code = "MIC_ERROR"
    message = "Unable to access microphone. Check Settings > Privacy."
```

**What to do:**
- [ ] Replace `print()` with `logger.info()`, `logger.error()`
- [ ] Define error code enum (`backend/errors.py`)
- [ ] Return error codes to frontend instead of exception strings
- [ ] Add `/api/diagnostics/logs` endpoint to export logs (for support)
- [ ] Display user-friendly error messages in UI

**Success metric:** All errors have codes. No exception tracebacks leak to UI.

---

### 1.5 Storage & Backup: Safe Persistence

**Current state:** Multiple storage systems (SQLite, JSON, ChromaDB). No backup strategy.

**Target state:** Single source of truth, automatic backups, safe recovery.

**Implementation:**

```
~/.seven/
├── config/
│   ├── settings.json
│   ├── api_token
│   └── .onboarded
├── data/
│   ├── seven.db               # Main SQLite
│   ├── seven.db-wal
│   ├── backups/
│   │   ├── seven-2026-09-12.db
│   │   ├── seven-2026-09-11.db
│   │   └── seven-2026-09-10.db  # Keep last 7 daily + last 30 weekly
│   └── memory/
│       └── chroma.db
└── logs/
    └── seven.log
```

**Backup strategy:**

```python
# backend/storage/backup.py
def create_backup(db_path: Path, backup_dir: Path):
    """Create timestamped backup. Keep last 7 daily + 4 weekly."""
    timestamp = datetime.now().strftime("%Y-%m-%d")
    backup_file = backup_dir / f"seven-{timestamp}.db"
    shutil.copy(db_path, backup_file)
    
    # Cleanup old backups
    backups = sorted(backup_dir.glob("seven-*.db"))
    if len(backups) > 11:  # 7 daily + 4 weekly
        for old in backups[:-11]:
            old.unlink()
```

**Recovery:**

```python
def restore_from_backup(backup_file: Path, db_path: Path):
    """Restore from backup with validation."""
    try:
        # Validate backup is not corrupted
        conn = sqlite3.connect(backup_file)
        conn.execute("PRAGMA integrity_check")
        conn.close()
        
        # Move current to trash, restore backup
        db_path.rename(db_path.with_suffix(".db.broken"))
        shutil.copy(backup_file, db_path)
    except Exception as e:
        raise BackupRestoreError(f"Failed to restore: {str(e)}")
```

**What to do:**
- [ ] Create backup on app launch (daily, automatic)
- [ ] Add `/api/backup/list` → show available backups
- [ ] Add `/api/backup/restore?file=seven-2026-09-10.db` with confirmation modal
- [ ] Add export-to-ZIP endpoint (`/api/backup/export`) for user downloads
- [ ] Add import endpoint for restoring exported backups

**Success metric:** User can restore a backup in 2 clicks. All backups are valid.

---

## Phase 2: Trust & Safety (Weeks 5-8)

### 2.1 Permissions & Approval Center

**What:**  
Add a dashboard showing what Seven can access and what actions it can take.

**Implementation:**

```
Dashboard > Settings > Permissions
├── Filesystem Access
│   └── [✓] Index C:\Users\you\Documents
│   └── [✓] Index C:\Users\you\Downloads
│   └── [ ] Access C:\Users\you\AppData
├── Application Control
│   └── [✓] Launch applications
│   └── [✓] Minimize/maximize windows
│   └── [ ] Close applications
├── System Control
│   └── [✓] Set reminders (Windows notifications)
│   └── [ ] Control volume
│   └── [ ] Sleep/lock computer
├── Voice & Microphone
│   └── [✓] Record and process audio locally
│   └── [ ] Transcribe to text (offline)
├── Dangerous Actions
│   └── [ ] Delete files
│   └── [ ] Send messages/emails
│   └── [ ] Modify system settings
```

**What to do:**
- [ ] Create permission schema in SQLite
- [ ] Add UI to toggle permissions per category
- [ ] Enforce permission checks in action router
- [ ] Add confirmation modal for sensitive actions
- [ ] Show "Remember this choice?" checkbox for sensitive + above

---

### 2.2 Voice & Microphone Health

**What:**  
Real-time voice diagnostics to build user confidence.

**Implementation:**

```
Dashboard > Voice Status
├── Microphone: Connected ✓
│   ├── Level: ████████░░ 82%
│   └── [Test Mic]
├── Voice Model: Llama 2 7B
│   ├── Status: Ready ✓
│   ├── VRAM: 6.2 / 8 GB
│   └── Response time: 1.2s
├── Wake Word: "Seven"
│   ├── Status: Listening ✓
│   └── Last triggered: 2 min ago
└── Recognition Confidence: 96% (last 10 queries)
```

**What to do:**
- [ ] Add `/api/diagnostics/voice-health` endpoint
- [ ] Add `/api/diagnostics/model-status` endpoint
- [ ] Create `frontend/src/components/VoiceHealth.jsx`
- [ ] Show real-time indicators on dashboard
- [ ] Add troubleshooting links ("Microphone not working?")

---

### 2.3 Offline Mode & Graceful Degradation

**What:**  
User understands what works offline vs. requires internet.

**Target:**
- ✓ Voice input (local STT)
- ✓ Task management
- ✓ App launching
- ✓ Window control
- ✗ Weather, web search, API calls
- ✗ Cloud sync (if added later)

**What to do:**
- [ ] Add offline detection in frontend (`navigator.onLine`)
- [ ] Show banner: "Offline — limited features available"
- [ ] Disable web-dependent features
- [ ] Queue actions for sync when back online

---

## Phase 3: Scale & Polish (Weeks 9-12)

### 3.1 Testing & QA

**What to do:**
- [ ] Add pytest tests for action execution, auth, backup
- [ ] Add Playwright tests for onboarding, panel UI, voice input
- [ ] Add linting/type-checking in CI (mypy, eslint)
- [ ] Document test data and fixtures
- [ ] Set up GitHub Actions CI (test on push)

---

### 3.2 Crash Reporting & Diagnostics

**What to do:**
- [ ] Add Sentry or equivalent (privacy-first error tracking)
- [ ] Add `/api/diagnostics/export` to download logs, config, system info
- [ ] Add "Send Diagnostics" button in Settings
- [ ] Make diagnostics export optional and transparent

---

### 3.3 Release & Update Strategy

**What to do:**
- [ ] Sign releases (code signing certificate for Windows)
- [ ] Implement auto-updater with delta updates
- [ ] Test rollback if update fails
- [ ] Create release notes template
- [ ] Version: semantic (major.minor.patch)

---

## Phase 4: Feature Completeness (Weeks 13+)

### 4.1 High-Impact Features

**Priority order:**

1. **Context-aware desktop assistant**
   - Summarize active app/website
   - "Reply to this email"
   - "Save this into my notes"

2. **Workspace templates**
   - "Developer mode" → open IDE, terminal, docs
   - "Meeting mode" → minimize distractions, launch Teams/Slack
   - "Focus mode" → block notifications, timer

3. **Advanced document ingestion**
   - PDF, DOCX, TXT, Markdown
   - Auto-index with drag & drop
   - Show source citations in responses

4. **Multi-device cloud sync** (optional, opt-in)
   - Sync tasks/memory to cloud vault
   - Optional, clearly labeled as cloud feature
   - Strong encryption, user controls

5. **Accessibility improvements**
   - Keyboard-only workflow
   - Screen reader support
   - High-contrast mode
   - Text size adjustment

---

## Success Criteria: Before Public Launch

### Reliability Checklist
- [ ] 99.9% uptime in 48-hour test (no crashes)
- [ ] All actions logged and reversible
- [ ] Microphone failures handled gracefully
- [ ] Model loading timeouts → clear UX (not frozen)
- [ ] Backup/restore tested and documented

### Security Checklist
- [ ] API token required for all mutations
- [ ] CORS restricted to Electron origin
- [ ] No credentials in logs or error messages
- [ ] No telemetry without opt-in consent
- [ ] Security.md published with reporting policy

### UX Checklist
- [ ] Onboarding completes in <5 minutes
- [ ] First 3 commands work without documentation
- [ ] Error messages are actionable, not technical
- [ ] All primary workflows keyboard-accessible
- [ ] Help documentation complete

### Operations Checklist
- [ ] Automated tests pass locally and in CI
- [ ] Crash reports go to private Sentry
- [ ] Release process automated (sign, upload, notify)
- [ ] Rollback procedure documented and tested
- [ ] Support runbook exists (common issues)

---

## Monitoring & Feedback Loop

**What to do:**
- [ ] Set up weekly usage metrics dashboard
- [ ] Collect feature requests via in-app feedback form
- [ ] Monitor Sentry for top errors
- [ ] Track onboarding completion rate
- [ ] Survey early users monthly

---

## Estimated Timeline

| Phase | Duration | Team Size | Output |
|-------|----------|-----------|--------|
| Foundation (Reliability, Security, UX) | 4 weeks | 1–2 | Production-ready core |
| Trust (Permissions, Voice health, Offline) | 3 weeks | 1–2 | User confidence |
| Scale (Testing, Diagnostics, Updates) | 4 weeks | 2–3 | Enterprise readiness |
| Features (Context, Workspaces, Sync) | 4+ weeks | 2–3 | Full product |
| **Total** | **15+ weeks** | | **Public launch** |

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Model loading slow | Bundled quantized model, progress tracking, offline fallback |
| Microphone access denied | Test on first run, clear OS permission flow, graceful fallback to text |
| Action fails (can't open app) | Log reason, show user-friendly message, offer retry |
| Data loss | Daily auto-backup, easy restore, import/export |
| Security vulnerability | Security.md with responsible disclosure, rapid patch, auto-update |
| User confusion | Onboarding covers 90% of common actions, in-app help, tutorial videos |

---

## Conclusion

Seven has strong product-market fit potential. This roadmap transforms it from an impressive prototype into a trusted, professional product worthy of millions of users who value privacy and local control.

**Next step:** Pick one item from Phase 1.1–1.5, implement it fully, test it, and commit to main.

