"""Feedback goes to the Google Form through the backend, reports honestly, and queues when offline."""
import os
import tempfile
import unittest
from unittest import mock

from support import BrainTest  # noqa: F401  (sets up an isolated environment)


class Feedback(unittest.TestCase):
    def setUp(self):
        try:
            from backend.routes import feedback
        except Exception:
            self.skipTest("backend routes need fastapi")
        self.f = feedback
        self.queue = os.path.join(tempfile.mkdtemp(), "queue.json")
        patcher = mock.patch.object(feedback, "_queue_path", return_value=self.queue)
        patcher.start()
        self.addCleanup(patcher.stop)

    def send(self, accepted):
        with mock.patch.object(self.f, "_post", return_value=accepted) as post:
            out = self.f.send_feedback(self.f.FeedbackIn(category="Bug Report", severity="High",
                                                          details="The orb froze", include_app_info=False))
        return out, post

    def test_viewform_link_is_turned_into_the_submit_url(self):
        self.assertTrue(self.f._form_url().endswith("/formResponse"))
        self.assertTrue(self.f._configured())

    def test_sent_only_when_google_accepts(self):
        out, post = self.send(True)
        self.assertEqual(out, {"sent": True, "queued": 0})
        self.assertEqual(post.call_args[0][0]["details"], "The orb froze")

    def test_offline_feedback_is_queued_and_retried(self):
        out, _ = self.send(False)
        self.assertEqual(out, {"sent": False, "queued": 1})
        self.assertEqual(self.f.feedback_status()["queued"], 1)
        with mock.patch.object(self.f, "_post", return_value=True):
            self.assertEqual(self.f.retry_feedback()["queued"], 0)

    def test_app_info_is_appended_only_when_allowed(self):
        with mock.patch.object(self.f, "_post", return_value=True) as post:
            self.f.send_feedback(self.f.FeedbackIn(category="Other", details="Hello there", include_app_info=True))
        self.assertIn("[Seven ", post.call_args[0][0]["details"])


if __name__ == "__main__":
    unittest.main()
