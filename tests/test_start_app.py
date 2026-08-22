import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import start_app  # noqa: E402


class StartAppTests(unittest.TestCase):
    def test_library_files_only_returns_papers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "paper.pdf").touch()
            (root / "slides.pptx").touch()
            (root / "notes.txt").touch()
            self.assertEqual(
                [path.name for path in start_app.library_files(root)],
                ["paper.pdf", "slides.pptx"],
            )

    def test_available_port_skips_an_occupied_port(self):
        class Probe:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def bind(self, address):
                if address[1] == 8000:
                    raise OSError("occupied")

        with patch.object(start_app.socket, "socket", return_value=Probe()):
            self.assertEqual(start_app.available_port(8000), 8001)


if __name__ == "__main__":
    unittest.main()
