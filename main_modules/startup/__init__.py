"""
main_modules/startup/
Startup and runtime helpers for main.py.

Modules:
  context.py           — SevenContext shared runtime state
  module_loader.py     — loads ears, brain, hands, mouth, memory
  morning_brief.py     — builds and speaks startup briefing
  battery_monitor.py   — background battery watching
  daemon_launcher.py   — spawns schedule_daemon.py if not running
  enrollment_handler.py — handles voice enrollment flow
"""