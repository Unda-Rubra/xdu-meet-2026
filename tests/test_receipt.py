import json
from pathlib import Path
import tempfile
import unittest
from raceops.exporter import verify_receipt
from raceops.model import canonical_hash
from raceops.assets import digest


class ArchiveReceiptTests(unittest.TestCase):
    def test_manifest_without_snapshot_cannot_authorize_reset(self):
        state = {"state": "STOPPED", "attempt_id": "a", "revision": 7}
        manifest = {"schema_version": 1, "complete": True, "files": {}, "servers": {
            "race-a": {"snapshot_hash": canonical_hash(state), "attempt_id": "a", "revision": 7, "snapshot_file": "race-a.json"}}}
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                verify_receipt(path, {"race-a": state})

    def test_stale_snapshot_cannot_claim_newer_revision_hash(self):
        stored = {"state": "STOPPED", "attempt_id": "a", "revision": 6}
        state = {**stored, "revision": 7}
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            snapshot = path / "race-a.json"
            snapshot.write_text(json.dumps({"snapshot": stored}))
            manifest = {"schema_version": 1, "complete": True, "files": {"race-a.json": digest(snapshot)},
                        "servers": {"race-a": {"snapshot_hash": canonical_hash(state), "attempt_id": "a",
                                              "revision": 7, "snapshot_file": "race-a.json"}}}
            (path / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "archived snapshot"):
                verify_receipt(path, {"race-a": state})


if __name__ == '__main__':
    unittest.main()
