import unittest
from pathlib import Path
class PRMarkerTests(unittest.TestCase):
    def test_open(self): self.assertEqual(Path('AUTONOMY_PR_OPEN_MARKER').read_text().strip(), 'OPEN')
if __name__ == '__main__': unittest.main()
