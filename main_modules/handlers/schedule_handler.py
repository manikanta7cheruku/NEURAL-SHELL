"""
main_modules/handlers/schedule_handler.py

Handles ###SCHED: tags.
Actions: alarm, reminder, timer, event, cancel, list, timer_remaining.

Enforces plan limits (recurring, total schedules).
"""

from colorama import Fore
from main_modules.handlers.base import BaseHandler


class ScheduleHandler(BaseHandler):
    tag_name = "SCHED"

    def execute(self, response, ctx):
        for params in self.extract_params(response):
            # Inject speaker_id for scheduler
            params["speaker_id"] = ctx.speaker_id

            action = params.get("action", "")

            # Plan limit checks for creation actions
            if action in ("alarm", "reminder", "timer", "event"):
                if not self._check_plan_limits(params, ctx):
                    continue

            try:
                success, msg = ctx.scheduler_mod.manage_schedule(params)

                # Telemetry
                try:
                    import telemetry
                    telemetry.log_activity()
                except Exception:
                    pass

                if success:
                    ctx.update_status(f"Schedule: {msg}", "#00ff00")

                    # Only speak scheduler confirmation if brain gave no speech part
                    # brain already said "On it." or "Locked in." before the tag
                    if msg and not ctx.speech_part and any(x in msg for x in [
                        "AM", "PM", "today", "tomorrow", "minutes", "seconds",
                        "hours", "Monday", "Tuesday", "Wednesday", "Thursday",
                        "Friday", "Saturday", "Sunday"
                    ]):
                        if ctx.speak_with_interrupt:
                            ctx.speak_with_interrupt(msg)
                        else:
                            ctx.speak(msg)
                else:
                    ctx.speak(msg)
                    ctx.update_status(f"Schedule failed: {msg}", "#ff0000")

            except Exception as e:
                print(Fore.RED + f"[SCHED HANDLER] Error: {e}")
                import traceback
                traceback.print_exc()

    def _check_plan_limits(self, params, ctx):
        """Returns True if allowed to create schedule, False if plan limit hit."""
        try:
            import voice_limits

            recur = params.get("recur", "")
            if recur and recur not in ("", "none"):
                rec_ok, rec_msg = voice_limits.check_bool("recurring_schedules")
                if not rec_ok:
                    ctx.speak(rec_msg)
                    ctx.update_status("PLAN LIMIT", "#ffaa00")
                    return False

            current_scheds = ctx.scheduler_mod.get_active_count()
            sched_ok, sched_msg = voice_limits.check("schedules", current_scheds)
            if not sched_ok:
                ctx.speak(sched_msg)
                ctx.update_status("PLAN LIMIT", "#ffaa00")
                return False

        except Exception:
            pass  # Graceful degradation — allow through if limit check fails

        return True