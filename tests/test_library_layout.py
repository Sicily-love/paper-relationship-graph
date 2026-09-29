import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import library_layout  # noqa: E402


class LibraryLayoutTests(unittest.TestCase):
    def test_active_scan_excludes_archives_hidden_folders_and_project_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / "paper-relationship-graph"
            project.mkdir()
            category = root / library_layout.STANDARD_CATEGORIES[0]
            category.mkdir()
            (category / "active.pdf").touch()
            (root / "new-paper.pdf").touch()
            (root / library_layout.ARCHIVE_LIBRARY_DIR).mkdir()
            (root / library_layout.ARCHIVE_LIBRARY_DIR / "archived.pdf").touch()
            (root / ".runtime").mkdir()
            (root / ".runtime" / "asset.pdf").touch()
            (project / "fixture.pdf").touch()

            files = library_layout.paper_files(root, excluded_roots=(project,))

            self.assertEqual(
                [path.relative_to(root).as_posix() for path in files],
                [f"{category.name}/active.pdf", "new-paper.pdf"],
            )

    def test_partition_separates_standard_and_unclassified_papers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            category = root / library_layout.STANDARD_CATEGORIES[0]
            category.mkdir()
            categorized = category / "categorized.pdf"
            unclassified = root / "unclassified.pdf"
            categorized.touch()
            unclassified.touch()

            recognized, pending = library_layout.partition_by_taxonomy(root)

            self.assertEqual(recognized, [categorized])
            self.assertEqual(pending, [unclassified])


if __name__ == "__main__":
    unittest.main()
