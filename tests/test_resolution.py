from __future__ import annotations

import unittest

import conftest  # noqa: F401 - installs package and ComfyUI paths
from Krea2OneNode.resolution import resolution_for_megapixels, validate_dimensions


class ResolutionTests(unittest.TestCase):
    def test_megapixel_resolution_is_aligned_and_close(self) -> None:
        for aspect, megapixels in (("1:1", 1.0), ("16:9", 0.98), ("9:16", 1.0), ("21:9", 1.5)):
            with self.subTest(aspect=aspect, megapixels=megapixels):
                width, height = resolution_for_megapixels(aspect, megapixels, 32)
                self.assertEqual(width % 32, 0)
                self.assertEqual(height % 32, 0)
                self.assertLess(abs(width * height / 1_000_000 - megapixels), 0.08)

    def test_invalid_dimensions_are_not_silently_aligned(self) -> None:
        with self.assertRaisesRegex(ValueError, "divisible"):
            validate_dimensions(1025, 1024, 8)
