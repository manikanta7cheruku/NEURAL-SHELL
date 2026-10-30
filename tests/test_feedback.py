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

    def test_the_form_has_only_email_and_message_so_the_category_leads_the_message(self):
        entry = {"category": "Bug Report", "severity": "Critical", "details": "The orb froze", "email": "a@b.co"}
        self.assertEqual(self.f.compose_message(entry), "[Bug Report, Critical]\n\nThe orb froze")
        self.assertEqual(self.f.compose_message({**entry, "severity": "N/A"}), "[Bug Report]\n\nThe orb froze")
        self.assertEqual(set(self.f._fields()), {"email", "message"})
        with mock.patch("requests.post") as post:
            post.return_value = mock.Mock(status_code=200, text="Your response has been recorded")
            self.assertTrue(self.f._post(entry))
        sent = post.call_args.kwargs["data"]
        self.assertEqual(sent, {"entry.1666026261": "a@b.co", "entry.480930978": "[Bug Report, Critical]\n\nThe orb froze"})

    def test_the_name_travels_with_the_report_and_gets_its_own_column_when_the_form_has_one(self):
        entry = {"category": "Other", "severity": "", "details": "Hello there", "email": "a@b.co", "name": "Asha"}
        self.assertEqual(self.f.compose_message(entry), "[Other]\nFrom: Asha\n\nHello there")
        with mock.patch("requests.post") as post:
            post.return_value = mock.Mock(status_code=200, text="Your response has been recorded")
            self.f._post(entry)
            self.assertEqual(set(post.call_args.kwargs["data"]), {"entry.1666026261", "entry.480930978"})
            with mock.patch.dict(os.environ, {"SEVEN_FEEDBACK_FIELDS": '{"name": "entry.5", "category": "entry.6", "severity": "entry.7"}'}):
                self.f._post(entry)
        sent = post.call_args.kwargs["data"]
        self.assertEqual((sent["entry.5"], sent["entry.6"], sent["entry.7"]), ("Asha", "Other", "N/A"))

    def test_app_info_is_appended_only_when_allowed(self):
        with mock.patch.object(self.f, "_post", return_value=True) as post:
            self.f.send_feedback(self.f.FeedbackIn(category="Other", details="Hello there", include_app_info=True))
        self.assertIn("[Seven ", post.call_args[0][0]["details"])


if __name__ == "__main__":
    unittest.main()
