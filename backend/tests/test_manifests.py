import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from incident_lens.validation.manifests import ManifestError, validate_directory, validate_manifest
from incident_lens.validation.local import check_links, check_privacy


ROOT = Path(__file__).parents[2]


class ManifestValidationTests(unittest.TestCase):
    def test_audited_manifests_validate_without_raw_data(self):
        paths = validate_directory(ROOT / "data/manifests")
        self.assertEqual(len(paths), 5)
        for path in paths:
            self.assertFalse(json.loads(path.read_text())["raw_data_in_repo"])

    def test_filename_leakage_is_rejected(self):
        data = json.loads((ROOT / "data/manifests/development.json").read_text())
        data["cases"][0]["source_filename"] = "re2ob_service_cpu_1"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ManifestError, "leakage"):
                validate_manifest(path)

    def test_hidden_label_leakage_is_rejected(self):
        data = json.loads((ROOT / "data/manifests/development.json").read_text())
        data["cases"][0]["hidden_label"] = "service-a"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ManifestError, "leakage"):
                validate_manifest(path)

    def test_repository_links_and_privacy_boundary_are_clean(self):
        paths = [ROOT / "README.md", ROOT / "docs", ROOT / "backend", ROOT / "contracts", ROOT / "data", ROOT / ".env.example", ROOT / "frontend/src"]
        self.assertEqual(check_links(paths), [])
        self.assertEqual(check_privacy(paths), [])


if __name__ == "__main__":
    unittest.main()
