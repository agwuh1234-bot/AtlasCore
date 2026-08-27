import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
INDEX = WEB / "index.html"


class _AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "link" and values.get("href"):
            self.assets.append(values["href"])
        elif tag == "script" and values.get("src"):
            self.assets.append(values["src"])


def _local_asset_path(value: str):
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return None
    path = parsed.path
    if path.startswith("/app/"):
        return WEB / path.removeprefix("/app/")
    return None


class WebAssetIntegrityTests(unittest.TestCase):
    def _assets(self):
        parser = _AssetParser()
        parser.feed(INDEX.read_text(encoding="utf-8"))
        return parser.assets

    def test_all_local_index_assets_exist(self):
        missing = []
        for asset in self._assets():
            local = _local_asset_path(asset)
            if local is not None and not local.is_file():
                missing.append(asset)
        self.assertEqual(missing, [], f"index.html references missing local assets: {missing}")

    def test_local_index_assets_are_not_duplicated(self):
        local_assets = [
            asset
            for asset in self._assets()
            if _local_asset_path(asset) is not None
        ]
        duplicates = sorted({asset for asset in local_assets if local_assets.count(asset) > 1})
        self.assertEqual(duplicates, [], f"index.html includes duplicate local assets: {duplicates}")

    def test_reference_v2_stylesheet_and_script_are_both_loaded(self):
        assets = self._assets()
        self.assertIn("/app/reference-v2.css", assets)
        self.assertIn("/app/reference-v2.js", assets)


if __name__ == "__main__":
    unittest.main()
