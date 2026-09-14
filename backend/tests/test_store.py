import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from incident_lens.api.store import StateStore
from incident_lens.fixtures.loader import load_cases


class SQLiteStoreOwnershipTests(unittest.TestCase):
    def test_save_report_rejects_non_owner_session_at_store_boundary(self):
        with tempfile.NamedTemporaryFile(suffix=".sqlite3") as database:
            store = StateStore(database.name)
            try:
                store.seed_cases(load_cases())
                owner = store.create_session()["session_id"]
                other = store.create_session()["session_id"]
                run = store.create_run(owner, "checkout-failure", {"execution": "new_analysis"}, "ownership-run")
                with self.assertRaisesRegex(ValueError, "does not own"):
                    store.save_report(other, run["run_id"], {"execution": "new_analysis"}, [], "ownership-report")
                self.assertEqual(store.get_report("not-created"), None)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
