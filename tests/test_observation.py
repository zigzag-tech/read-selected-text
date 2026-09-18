import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "read_selected_text"))

import backend
import daemon
from observation import ObservationRecorder


class _Response:
    def __init__(self, chunks):
        self.chunks = iter(chunks)

    def read1(self, _size):
        return next(self.chunks, b"")


class _Input:
    def __init__(self):
        self.writes = []

    def write(self, value):
        self.writes.append(value)

    def flush(self):
        pass

    def close(self):
        pass


class _Player:
    def __init__(self):
        self.stdin = _Input()

    def wait(self):
        return 0

    def poll(self):
        return 0


class ObservationTest(unittest.TestCase):
    def test_disabled_recorder_writes_nothing(self):
        recorder = ObservationRecorder(path=None, request_id="r1")
        recorder.offer("requested", input_bytes=10)
        self.assertEqual(recorder.drain(), [])

    def test_metadata_is_bounded_and_rejects_content_fields(self):
        recorder = ObservationRecorder(path=None, request_id="r1", max_records=1,
                                       enabled=True)
        self.assertTrue(recorder.offer("requested", input_bytes=10))
        self.assertFalse(recorder.offer("requested", input_bytes=11))
        with self.assertRaises(ValueError):
            recorder.offer("requested", text="private")
        self.assertEqual(recorder.dropped_count, 1)

    def test_flush_is_opt_in_bounded_and_contains_no_speech_content(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "observations.jsonl"
            recorder = ObservationRecorder(path=path, request_id="r1",
                                           max_file_bytes=2048)
            recorder.offer("requested", input_bytes=len(b"private marker"))
            recorder.flush()
            payload = path.read_text()
            self.assertIn('"kind": "requested"', payload)
            self.assertNotIn("private marker", payload)

            full = ObservationRecorder(path=path, request_id="r2",
                                       max_file_bytes=path.stat().st_size)
            full.offer("requested", input_bytes=1)
            full.flush()
            self.assertEqual(path.read_text(), payload)

    def test_play_records_first_audible_after_audio_is_submitted(self):
        recorder = ObservationRecorder(path=None, request_id="r1", enabled=True)
        player = _Player()
        with mock.patch.object(backend.subprocess, "Popen", return_value=player), \
                mock.patch.object(backend, "notify"):
            self.assertTrue(backend.play(_Response([b"pcm", b""]), 24000,
                                         "speaking", recorder=recorder,
                                         attempt_id="a1", backend_name="harmony"))
        record = next(item for item in recorder.drain()
                      if item["kind"] == "first_audible")
        self.assertEqual(record["attempt_id"], "a1")
        self.assertEqual(record["backend"], "harmony")
        self.assertEqual(player.stdin.writes, [b"pcm"])

    def test_local_fallback_is_attributed_after_harmony_failure(self):
        recorder = ObservationRecorder(path=None, request_id="r1", enabled=True)
        with mock.patch.object(backend, "remote_speech", side_effect=OSError("down")), \
                mock.patch.object(backend, "local_speech", return_value=True):
            result = backend.speak("private marker", {
                "targets": [{"admit": "x"}], "voice_id": "v",
                "harmony_timeout_seconds": 1,
            }, recorder)
        self.assertEqual(result, 0)
        served = next(item for item in recorder.drain() if item["kind"] == "served")
        self.assertEqual(served["backend"], "piper")
        self.assertEqual(served["fallback_kind"], "harmony_failed")
        self.assertNotIn("private marker", json.dumps(served))

    def test_shortcut_stop_records_cancellation_for_active_request(self):
        recorder = ObservationRecorder(path=None, request_id="daemon", enabled=True)
        proc = mock.Mock(pid=123)
        proc.poll.return_value = None
        with daemon.state_lock:
            daemon.player = proc
            daemon.active_request_id = "request-7"
        with mock.patch.object(daemon.os, "killpg"), \
                mock.patch.object(daemon.subprocess, "run"):
            daemon.stop(recorder=recorder)
        canceled = recorder.drain()[-1]
        self.assertEqual(canceled["kind"], "canceled")
        self.assertEqual(canceled["request_id"], "request-7")
        self.assertEqual(canceled["cancel_cause"], "shortcut_toggle")


if __name__ == "__main__":
    unittest.main()
