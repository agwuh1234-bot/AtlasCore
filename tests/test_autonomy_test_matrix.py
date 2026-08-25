import unittest
from pathlib import Path


class MatrixTests(unittest.TestCase):
    def test_matrix_covers_core_areas(self):
        text = Path("AUTONOMY_TEST_MATRIX.md").read_text(encoding="utf-8")
        for area in ("Engine", "Persistence", "Workers", "Runtime", "Integration", "Security", "Operations"):
            self.assertIn(f"| {area} |", text)


if __name__ == "__main__":
    unittest.main()
