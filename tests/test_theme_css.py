from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "web" / "css" / "krea2_one_node.css").read_text(encoding="utf-8")
UI = (ROOT / "web" / "js" / "ui.js").read_text(encoding="utf-8")


class ThemeCssTests(unittest.TestCase):
    def test_every_theme_defines_full_surface_palette(self):
        required_tokens = (
            "--surface-header",
            "--surface-controls",
            "--surface-block",
            "--surface-input",
            "--surface-preview",
            "--surface-preview-toolbar",
            "--surface-preview-footer",
            "--surface-prompt",
            "--surface-card",
        )
        for theme in ("red-fire", "blue-snow", "crimson", "glass", "black"):
            start = CSS.index(f'.k2-app[data-theme="{theme}"]')
            end = CSS.index("}\n", start)
            theme_block = CSS[start:end]
            for token in required_tokens:
                self.assertIn(token, theme_block, f"{theme} is missing {token}")

    def test_glass_theme_uses_translucency_and_backdrop_blur(self):
        self.assertIn('background: rgba(10,21,35,.66);', CSS)
        self.assertIn('backdrop-filter: blur(24px) saturate(1.15);', CSS)
        self.assertIn('.k2-app[data-theme="glass"] :is(', CSS)
        self.assertIn('.k2-viewport,', CSS)
        self.assertIn('backdrop-filter: blur(20px) saturate(1.32);', CSS)

    def test_theme_updates_outer_canvas_node_and_keeps_output_matte_black(self):
        for theme in ("red-fire", "blue-snow", "crimson", "glass", "black"):
            self.assertIn(f'"{theme}": {{title:', UI)
        self.assertIn('applyCanvasNodeTheme(node,root.dataset.theme)', UI)
        self.assertIn('.k2-app .k2-viewport.has-output,', CSS)
        self.assertIn('background: #000;', CSS)

    def test_unlock_scan_keeps_its_geometry_and_cleans_up(self):
        coverage_start = CSS.index("/* Theme coverage:")
        scan_start = CSS.index(".k2-app::after {", coverage_start)
        scan_end = CSS.index("}\n", scan_start)
        themed_scan = CSS[scan_start:scan_end]
        self.assertIn("background-image:", themed_scan)
        self.assertNotIn("\n  background:", themed_scan)
        self.assertIn("background-size: 300% 100%;", CSS)
        self.assertIn(".k2-app.is-unlocking::after {", CSS)
        self.assertIn("animation: k2-unlock-scan .72s .06s", CSS)
        self.assertIn("100% { opacity: 0; background-position: -100% 0; }", CSS)
        self.assertIn('root.classList.add("is-unlocking")', UI)
        self.assertIn('root.classList.remove("is-unlocking")', UI)
        self.assertIn('event.animationName==="k2-unlock-scan"', UI)

    def test_black_theme_and_stats_surface_are_complete(self):
        self.assertIn('.k2-overlay[data-theme="black"] .k2-modal', CSS)
        self.assertIn('.k2-stats-bar {', CSS)
        self.assertIn('"black": {title:', UI)

    def test_reduced_motion_disables_root_and_scan_animations(self):
        reduced = CSS[CSS.index("@media (prefers-reduced-motion: reduce)") :]
        self.assertIn(".k2-app::after,", reduced)
        self.assertIn("animation: none !important;", reduced)
        self.assertIn("display: none !important;", reduced)


if __name__ == "__main__":
    unittest.main()
