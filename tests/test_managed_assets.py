from __future__ import annotations

import unittest

import conftest  # noqa: F401 - installs package and ComfyUI paths

from Krea2OneNode.server import MANAGED_FILES, _asset_name_matches


class ManagedAssetTests(unittest.TestCase):
    def test_civitai_style_filenames_are_recognized(self) -> None:
        canon, cinematic = MANAGED_FILES[:2]
        self.assertTrue(_asset_name_matches(canon, "downloads/Krea2_Canon_UltraReal_v1.safetensors"))
        self.assertTrue(_asset_name_matches(cinematic, "Krea 2/Krea2_CinematicMovieStill_v3.safetensors"))

    def test_unrelated_loras_are_not_claimed_as_managed(self) -> None:
        canon, cinematic = MANAGED_FILES[:2]
        self.assertFalse(_asset_name_matches(canon, "Krea 2/portrait_realism.safetensors"))
        self.assertFalse(_asset_name_matches(cinematic, "Krea 2/cinematic_generic.safetensors"))

    def test_identity_edit_v12_filename_is_recognized(self) -> None:
        identity = next(item for item in MANAGED_FILES if item["id"] == "identity_edit_v1_2")
        self.assertTrue(_asset_name_matches(identity, "downloads/Krea2-Identity-Edit-v1_2.safetensors"))
        self.assertFalse(_asset_name_matches(identity, "Krea 2/krea2_identity_edit_v1_1.safetensors"))


if __name__ == "__main__":
    unittest.main()
