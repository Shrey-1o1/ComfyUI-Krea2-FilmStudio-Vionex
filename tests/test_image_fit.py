from __future__ import annotations

import unittest

import conftest  # noqa: F401 - installs package and ComfyUI paths
import torch

from Krea2OneNode.nodes import Krea2ImageFit


class ImageFitTests(unittest.TestCase):
    def test_all_fit_modes_return_exact_canvas_size(self) -> None:
        image = torch.ones((1, 80, 160, 3), dtype=torch.float32)
        for mode in ("crop", "fit", "stretch"):
            with self.subTest(mode=mode):
                result = Krea2ImageFit().resize(image, 128, 96, mode)[0]
                self.assertEqual(tuple(result.shape), (1, 96, 128, 3))

    def test_fit_mode_preserves_whole_image_with_letterbox(self) -> None:
        image = torch.ones((1, 64, 192, 3), dtype=torch.float32)
        result = Krea2ImageFit().resize(image, 128, 128, "fit")[0]
        self.assertEqual(float(result[:, 0].max()), 0.0)
        self.assertGreater(float(result[:, 64].mean()), 0.9)

