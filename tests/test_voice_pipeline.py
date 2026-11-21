"""
The voice pipeline end to end, without a microphone or a model: sound becomes utterances (the speech detector's scores stand in for
audio), text is judged real or noise, a request said over Seven is kept, and everything thrown away says so.

Each test is a way Seven used to ignore or lose something a person said.
"""
import json
import os
import queue
import re
import unittest

import numpy as np

import support  # noqa: F401  (sets up paths and test mode)
from ears import barge_in
from ears.gpu_guard import is_gpu_error
from ears.hallucination_filter import is_hallucination, is_incoherent, is_repetition_loop
from ears.stream import MIN_SPEECH_S, MicStream

GUIDE = os.path.join(support.ROOT, "frontend", "src", "guide", "guide.json")


def verdict(text, answering=False):
    """What the ears' text filters say about a transcript: "" when it goes on to be acted on, else why not."""
    clean = re.sub(r"[.!,?]+", "", text.lower()).strip()
    ghost, why = is_hallucination(clean, text.lower(), answering)
    if ghost:
        return why
    return "repetition loop" if is_repetition_loop(clean) else "incoherent" if is_incoherent(clean) else ""


class TextFilters(unittest.TestCase):
    def test_every_phrase_the_guide_teaches_is_accepted(self):
        with open(GUIDE, encoding="utf-8") as f:
            data = json.load(f)
        phrases = [x["say"] for x in data["tryIt"]] + [e["say"] for g in data["groups"] for e in g["examples"]]
        refused = [(p, verdict(p)) for p in phrases if verdict(p)]
        self.assertEqual(refused, [])                         # "Open downloads" and "Remind me to stretch in 20 minutes" were refused

    def test_a_request_that_starts_like_noise_is_still_a_request(self):
        for text in ("Okay open Chrome", "I want to open chrome", "you can open chrome", "The weather today", "A reminder for tomorrow",
                     "So what time is it", "Um open chrome", "Uh what's the weather", "Well, set a timer for ten minutes",
                     "Yeah open notepad", "Thanks, that's all", "Thank you Seven", "Hmm what time is it", "Bye Seven"):
            self.assertEqual(verdict(text), "", text)         # a "starts with a hallucination" rule used to refuse all of these

    def test_a_request_that_names_a_shop_or_a_folder_is_not_an_advertisement(self):
        for text in ("Open amazon", "Order a pizza on swiggy", "Visit youtube", "Download chrome", "Play some music on amazon music",
                     "Remind me to call mom at 5", "Open downloads"):
            self.assertEqual(verdict(text), "", text)

    def test_what_comes_out_of_a_tv_or_silence_is_still_refused(self):
        for text in ("thank you", "thanks for watching", "thank you bye bye", "you", "the", "www.google.com", "subscribe to my channel and like",
                     "amara.org subtitles", "la la la la", "ba ba ba ba", "10th 7th 8th 8th 8th", "Never go out of style, all the traditions",
                     "Swiggy order now limited time offer valid", "Buy now at amazon today limited time offer valid for all customers"):
            self.assertNotEqual(verdict(text), "", text)

    def test_thanks_and_okay_are_answers_when_seven_has_just_asked_or_spoken(self):
        for text in ("thanks", "thank you", "okay", "yeah", "bye"):
            self.assertNotEqual(verdict(text), "", text)                       # alone, out of nowhere: Whisper's invention
            self.assertEqual(verdict(text, answering=True), "", text)          # after Seven spoke: a person
        self.assertNotEqual(verdict("you", answering=True), "")                # never a request


class BargeIn(unittest.TestCase):
    def test_the_request_after_a_stop_word_is_kept(self):
        self.assertEqual(barge_in.request_after("Seven, what's the weather", "seven"), "what's the weather")
        self.assertEqual(barge_in.request_after("Hey Seven what time is it", "seven"), "what time is it")
        self.assertEqual(barge_in.request_after("stop, set a timer for five minutes", "stop"), "set a timer for five minutes")

    def test_a_bare_stop_word_or_one_not_at_the_start_keeps_nothing(self):
        self.assertEqual(barge_in.request_after("Seven", "seven"), "")
        self.assertEqual(barge_in.request_after("stop", "stop"), "")
        self.assertEqual(barge_in.request_after("what's the weather, wait", "wait"), "")


class GpuGuard(unittest.TestCase):
    def test_a_card_that_cannot_run_the_model_is_recognised_so_the_processor_takes_over(self):
        for message in ("Library cublas64_12.dll is not found or cannot be loaded", "cuDNN failed to initialize",
                        "CUDA failed with error out of memory", "no kernel image is available for execution on the device"):
            self.assertTrue(is_gpu_error(RuntimeError(message)), message)

    def test_other_failures_are_not_blamed_on_the_card(self):
        for message in ("could not broadcast input array", "invalid audio", "list index out of range"):
            self.assertFalse(is_gpu_error(ValueError(message)), message)


class Segmenting(unittest.TestCase):
    """Sound to utterances. A frame is 32 ms; the scores are what the speech detector would give: 0.9 speech, 0.05 silence."""

    def run_stream(self, probs):
        events = []
        s = MicStream()
        s.set_publisher(lambda k, v: events.append((k, v)))
        s._running.set()
        s._reopen = False
        frame = [0]

        class Fake:
            def read(self_, frames, exception_on_overflow=False):
                frame[0] += 1
                if frame[0] >= len(probs):
                    s._running.clear()
                return (np.ones(frames, dtype=np.int16) * 3000).tobytes()

        def vad(_):
            p = probs[min(frame[0] - 1, len(probs) - 1)]
            return p
        s._watch_silence = lambda *a, **k: False
        s._listen(Fake(), vad)
        out = []
        while True:
            try:
                out.append(s.utterances.get_nowait())
            except queue.Empty:
                return out, events, s

    def sentence(self, seconds):
        return [0.9] * int(seconds / 0.032)

    def test_yes_and_no_are_heard(self):
        # "yes": about 0.3 s of speech between silences. The old minimum was 0.35 s, so the answer to "shall I?" was "too short".
        got, events, _ = self.run_stream([0.05] * 20 + self.sentence(0.30) + [0.05] * 40)
        self.assertEqual(len(got), 1, events)
        self.assertGreaterEqual(MIN_SPEECH_S, 0.2)

    def test_a_click_is_still_not_a_word(self):
        got, events, _ = self.run_stream([0.05] * 20 + [0.9] * 4 + [0.05] * 40)
        self.assertEqual(got, [])

    def test_a_short_pause_inside_a_sentence_does_not_split_it(self):
        got, _, _ = self.run_stream([0.05] * 10 + self.sentence(1.0) + [0.05] * 12 + self.sentence(1.0) + [0.05] * 40)
        self.assertEqual(len(got), 1)

    def test_a_long_pause_ends_the_sentence(self):
        got, _, _ = self.run_stream([0.05] * 10 + self.sentence(1.0) + [0.05] * 40 + self.sentence(1.0) + [0.05] * 40)
        self.assertEqual(len(got), 2)

    def test_when_nobody_is_listening_the_oldest_is_dropped_and_it_is_said(self):
        probs = [0.05] * 10
        for _ in range(11):
            probs += self.sentence(0.8) + [0.05] * 30
        got, events, stream = self.run_stream(probs)
        self.assertEqual(len(got), 8)                                           # the queue holds eight
        self.assertGreaterEqual(stream.counts.get("dropped_busy", 0), 3)
        self.assertTrue(any(k == "voice_ignored" and "busy" in v["reason"] for k, v in events))


if __name__ == "__main__":
    unittest.main()
