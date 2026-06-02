import unittest

from shared import stable_id


class SharedStableIdTests(unittest.TestCase):
    def test_stable_id_matches_known_digest(self) -> None:
        self.assertEqual(stable_id("test", "alpha", "beta"), "test_2e146065b6f973953bf00962")

    def test_stable_id_separator_disambiguates_adjacent_parts(self) -> None:
        self.assertNotEqual(stable_id("test", "ab", "c"), stable_id("test", "a", "bc"))


if __name__ == "__main__":
    unittest.main()
