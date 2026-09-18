import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
SERVER = ROOT / "read_selected_text/piper_server.py"
BACKEND = ROOT / "read_selected_text/backend.py"


def load_server_functions():
    source = SERVER.read_text()
    start = source.index("def segments")
    end = source.index("\n\nclass Handler", start)
    namespace = {"MAX_CHARS": 20}
    exec(source[start:end], namespace)
    return namespace


class AppTest(unittest.TestCase):
    def test_chunks_are_bounded_and_preserve_words(self):
        segments = load_server_functions()["segments"]
        text = "Select text in any desktop application and hear it read aloud"
        chunks = list(segments(text))
        self.assertTrue(all(len(chunk) <= 20 for chunk in chunks))
        self.assertEqual(" ".join(chunks), text)

    def test_public_defaults_contain_no_network_targets_or_voice_id(self):
        common = (ROOT / "read_selected_text/common.py").read_text()
        self.assertIn('{"voice_id": "", "targets": []}', common)

    def test_services_only_use_user_paths(self):
        for unit in (ROOT / "systemd").glob("*.service"):
            source = unit.read_text()
            self.assertIn("%h/.local/share/read-selected-text", source)
            self.assertNotIn("/home/", source)

    def test_harmony_precedes_local_fallback_and_reports_backend(self):
        source = BACKEND.read_text()
        self.assertLess(source.index("for index, target in enumerate"),
                        source.index("if local_speech(text"))
        self.assertIn("backend=harmony-qwen", source)
        self.assertIn("backend=piper-cori", source)


if __name__ == "__main__":
    unittest.main()
