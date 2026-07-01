"""Basic metadata checks for the integration."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tomllib import load as load_toml

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_DIR = ROOT / "custom_components" / "wiener_luft"
MANIFEST_PATH = INTEGRATION_DIR / "manifest.json"
PYPROJECT_PATH = ROOT / "pyproject.toml"

REQUIRED_MANIFEST_KEYS = {
    "codeowners",
    "config_flow",
    "documentation",
    "domain",
    "iot_class",
    "issue_tracker",
    "name",
    "requirements",
    "single_config_entry",
    "version",
}


class MetadataTest(unittest.TestCase):
    def test_manifest_and_translations(self) -> None:
        self.assertTrue(INTEGRATION_DIR.is_dir())
        self.assertTrue(MANIFEST_PATH.is_file())

        with MANIFEST_PATH.open("r", encoding="utf-8") as file:
            manifest = json.load(file)

        self.assertTrue(REQUIRED_MANIFEST_KEYS.issubset(manifest))

        with PYPROJECT_PATH.open("rb") as file:
            project_data = load_toml(file)

        self.assertEqual(manifest["version"], project_data["project"]["version"])

        translations_dir = INTEGRATION_DIR / "translations"
        for locale in ("en", "de"):
            translation_path = translations_dir / f"{locale}.json"
            self.assertTrue(translation_path.is_file(), translation_path)
            with translation_path.open("r", encoding="utf-8") as file:
                json.load(file)
