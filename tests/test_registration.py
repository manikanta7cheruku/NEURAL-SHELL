"""
A person appears in the admin dashboard once the server has their name and email. The server may be asleep or the PC
offline, so registration retries until the server confirms, reads the identity as it is on disk now, and is sent again
only when the name or email changes.
"""
import os
import tempfile
import unittest
from unittest import mock

import support  # noqa: F401  (sets up paths and test mode)
import server_sync
import telemetry


class Registration(unittest.TestCase):
    def setUp(self):
        self.file = os.path.join(tempfile.mkdtemp(), "registered.json")
        self.sent = []
        self.identity = ("Asha", "asha@example.com", True)

        def register(payload, timeout=30):
            self.sent.append(payload)
            server_sync.last_error = "" if self.accept else "could not reach the server: ConnectTimeout"
            return self.accept

        self.accept = True
        for patcher in (mock.patch.object(telemetry, "REGISTERED_FILE", self.file),
                        mock.patch.object(telemetry, "_identity", lambda: self.identity),
                        mock.patch.object(telemetry, "get_device_id", lambda: "device-1"),
                        mock.patch.object(telemetry, "get_country_from_ip", lambda: "India"),
                        mock.patch.object(server_sync, "wake", lambda timeout=75: True),
                        mock.patch.object(server_sync, "register", register)):
            patcher.start()
            self.addCleanup(patcher.stop)
        telemetry._reg.update(last="", referral_code=None)

    def test_a_new_person_is_sent_with_their_name_and_email(self):
        self.assertTrue(telemetry.register_now())
        self.assertEqual(self.sent[0]["name"], "Asha")
        self.assertEqual(self.sent[0]["email"], "asha@example.com")
        self.assertTrue(telemetry.registration_status()["registered"])

    def test_it_is_not_sent_again_until_the_name_or_email_changes(self):
        telemetry.register_now()
        telemetry.register_now()
        self.assertEqual(len(self.sent), 1)
        self.identity = ("Asha K", "asha@example.com", True)
        telemetry.register_now()
        self.assertEqual(len(self.sent), 2)

    def test_a_sleeping_server_means_not_registered_yet_and_says_why(self):
        self.accept = False
        self.assertFalse(telemetry.register_now())
        status = telemetry.registration_status()
        self.assertFalse(status["registered"])
        self.assertIn("could not reach the server", status["last_error"])
        self.accept = True                                   # the server woke up: the next try succeeds
        self.assertTrue(telemetry.register_now())
        self.assertTrue(telemetry.registration_status()["registered"])

    def test_nothing_is_sent_before_setup_is_done_or_without_an_identity(self):
        self.identity = ("Asha", "asha@example.com", False)
        self.assertFalse(telemetry.register_now())
        self.identity = (None, None, True)
        self.assertFalse(telemetry.register_now())
        self.assertEqual(self.sent, [])

    def test_the_referral_code_travels_with_the_first_registration(self):
        telemetry._reg["referral_code"] = "SEVEN-ABC"
        telemetry.register_now()
        self.assertEqual(self.sent[0]["referral_code"], "SEVEN-ABC")


if __name__ == "__main__":
    unittest.main()
