from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "web" / "css" / "krea2_one_node.css").read_text(encoding="utf-8")
UI = (ROOT / "web" / "js" / "ui.js").read_text(encoding="utf-8")


class UiSourceTests(unittest.TestCase):
    def test_preview_zoom_is_not_overridden_by_image_animation(self) -> None:
        keyframes = CSS[CSS.index("@keyframes k2-image-in") : CSS.index("}", CSS.index("@keyframes k2-image-in")) + 1]
        self.assertNotIn("transform:", keyframes)
        self.assertIn("animation: k2-image-in .28s ease;", CSS)
        self.assertIn("outputImage.dataset.zoom=zoom.toFixed(3)", UI)
        self.assertIn("event.stopImmediatePropagation()", UI)
        self.assertIn("{passive:false,capture:true}", UI)

    def test_uploaded_references_have_a_remove_action(self) -> None:
        self.assertIn('button("Remove","k2-upload-clear")', UI)
        self.assertIn('store.set(path,"")', UI)
        self.assertIn(".k2-upload-clear {", CSS)

    def test_identity_edit_requires_automatic_v12_lora(self) -> None:
        self.assertIn('store.get("i2i.identity_lora")', UI)
        self.assertIn("Identity Edit v1.2 LoRA loads automatically", UI)

    def test_compare_slider_uses_first_uploaded_reference(self) -> None:
        self.assertIn('toggle("Compare"', UI)
        self.assertIn("firstComparableReference", UI)
        self.assertIn("k2-compare-divider", UI)
        self.assertIn("setComparePosition", UI)

    def test_reference_studio_exposes_four_images_and_examples(self) -> None:
        self.assertIn('references:["Reference Studio"', UI)
        self.assertIn("MULTI_REFERENCE_EXAMPLES", UI)
        self.assertIn('`uploads.image_${index}`', UI)
        self.assertIn('image_3:"IMAGE"', UI)
        self.assertIn('image_4:"IMAGE"', UI)

    def test_render_stats_measure_prompt_to_completion(self) -> None:
        self.assertIn("renderStartedAt=performance.now()", UI)
        self.assertIn("images_generated", UI)
        self.assertIn("Last prompt", UI)


if __name__ == "__main__":
    unittest.main()
