import tempfile
import unittest
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def test_only_reviewed_sources_are_delivered_with_matching_hashes(self):
        self.assertTrue((ROOT / 'pack.py').is_file(), 'whitelist packer is missing')
        import pack
        import hashlib
        import json
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'delivery.zip'
            pack.build_zip(target)
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(set(archive.namelist()), set(pack.FILES) | {'SHA256.json'})
                manifest = json.loads(archive.read('SHA256.json'))
                for name in pack.FILES:
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), manifest[name])
                    self.assertNotIn(''.join(('125', '34')), archive.read(name).decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
