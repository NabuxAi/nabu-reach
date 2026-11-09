"""Offline smoke checks for the WhatsApp connection center."""
import unittest
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]

class WhatsAppIntegrationUiTests(unittest.TestCase):
    def test_three_unique_connection_options_and_accessible_modal(self):
        html = (ROOT / "reach/web/index.html").read_text()
        for method in ("qr", "coexistence", "waba"):
            self.assertEqual(html.count(f'data-integration-method="{method}"'), 1)
            self.assertEqual(html.count(f'data-integration-detail="{method}"'), 1)
        self.assertIn('data-panel="integrations"', html)
        self.assertIn('role="dialog"', html)
        self.assertIn('aria-modal="true"', html)
        self.assertIn('id="integrationDialogTitle"', html)

    def test_no_fake_connection_or_send_action(self):
        html = (ROOT / "reach/web/index.html").read_text()
        script = (ROOT / "reach/web/app.js").read_text()
        self.assertIn("Official API setup placeholder only", script)
        self.assertIn("['qr','coexistence','waba']", script)
        self.assertIn("No live pairing", html)
        self.assertNotIn("Bulk sending without the ban risk", html)
        self.assertNotIn("Free blue tick", html)

    def test_demo_build_preserves_connection_guides(self):
        import subprocess
        import sys
        subprocess.run([sys.executable, "demo/build.py"], cwd=ROOT, check=True, capture_output=True)
        output=(ROOT / "dist/demo/index.html").read_text()
        self.assertIn('data-integration-method="waba"', output)
        self.assertIn('src="mock.js"', output)
        self.assertIn('src="app.js"', output)
        self.assertNotIn('src="/app.js"', output)

if __name__=="__main__":
    unittest.main()
