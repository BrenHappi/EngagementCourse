import unittest

from engagement_course.models import Category

TEST_CASES = [
    ("OPEN 1,2,3", [("OPEN", 1), ("OPEN", 2), ("OPEN", 3)]),
    ("ACCESS 1 ET 2", [("ACCESS", 1), ("ACCESS", 2)]),
    ("ACCESS 3 ET 4", [("ACCESS", 3), ("ACCESS", 4)]),
    ("OPEN 1,2,3 + ACCESS 1", [("OPEN", 1), ("OPEN", 2), ("OPEN", 3), ("ACCESS", 1)]),
    ("ACCESS 1", [("ACCESS", 1)]),
    ("OPEN 2,3 + ACCESS 1 ET 2", [("OPEN", 2), ("OPEN", 3), ("ACCESS", 1), ("ACCESS", 2)]),
    ("ACCESS 1,2,3,4", [("ACCESS", 1), ("ACCESS", 2), ("ACCESS", 3), ("ACCESS", 4)]),
    ("ELITE 12,2,3", []),  # catégorie non supportée -> ignorée
]


class TestCategories(unittest.TestCase):

    @staticmethod
    def _to_pairs(categories):
        return [(c.level, c.number) for c in categories]

    def test_parse_categories(self) -> None:
        for raw, expected in TEST_CASES:
            with self.subTest(raw=raw):
                categories = Category.from_string(raw)

                self.assertIsInstance(categories, list)
                self.assertEqual(self._to_pairs(categories), expected)

                for c in categories:
                    self.assertIn(c.level, {"OPEN", "ACCESS"})
                    self.assertIsInstance(c.number, int)


if __name__ == "__main__":
    unittest.main()