import tempfile
import unittest
from pathlib import Path

from deply.utils.ignore_parser import parse_ignore_comments, ALL_SUPPRESSION_RULES


class TestIgnoreParser(unittest.TestCase):
    def test_file_level_ignore(self):
        # Simulate a file with a file-level suppression comment.
        file_content = b"# deply:ignore-file:ENFORCE_INHERITANCE\nprint('hello world')\n"
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = Path(tmp.name)
        try:
            ignore_map = parse_ignore_comments(tmp_path)
            self.assertIn("ENFORCE_INHERITANCE", ignore_map["file"])
        finally:
            tmp_path.unlink()

    def test_file_level_ignore_blank(self):
        # Test file-level suppression with no specific rule (should add ALL_SUPPRESSION_RULES).
        file_content = b"# deply:ignore-file\nprint('hello world')\n"
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = Path(tmp.name)
        try:
            ignore_map = parse_ignore_comments(tmp_path)
            self.assertIn(ALL_SUPPRESSION_RULES, ignore_map["file"])
        finally:
            tmp_path.unlink()

    def test_line_level_ignore(self):
        # Simulate a file with a line-level suppression comment.
        file_content = b"print('test')  # deply:ignore:DISALLOW_LAYER_DEPENDENCIES\n"
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = Path(tmp.name)
        try:
            ignore_map = parse_ignore_comments(tmp_path)
            # The comment should be on line 1.
            self.assertIn("DISALLOW_LAYER_DEPENDENCIES", ignore_map["lines"].get(1, set()))
        finally:
            tmp_path.unlink()

    def test_line_level_ignore_blank(self):
        # Test line-level suppression with no specific rule.
        file_content = b"print('test')  # deply:ignore\n"
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = Path(tmp.name)
        try:
            ignore_map = parse_ignore_comments(tmp_path)
            self.assertIn(ALL_SUPPRESSION_RULES, ignore_map["lines"].get(1, set()))
        finally:
            tmp_path.unlink()


if __name__ == '__main__':
    unittest.main()
