import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
from api_auth import normalize_email  # noqa: E402


class QuotaDateTest(unittest.TestCase):
    def test_quota_date_uses_east_eight(self):
        if database.QUOTA_TIMEZONE != "Asia/Shanghai":
            self.skipTest("QUOTA_TIMEZONE 被环境变量覆盖")
        now = datetime.now(database.QUOTA_TZ)
        self.assertEqual(now.utcoffset(), timedelta(hours=8))
        self.assertEqual(database.quota_today(), now.strftime("%Y-%m-%d"))

    def test_quota_date_format(self):
        value = database.quota_today()
        self.assertRegex(value, r"^\d{4}-\d{2}-\d{2}$")


class EmailNormalizeTest(unittest.TestCase):
    def test_strip_and_lower(self):
        self.assertEqual(normalize_email("  Test@Example.COM "), "test@example.com")

    def test_empty(self):
        self.assertEqual(normalize_email(""), "")


class QuotaFlowTest(unittest.TestCase):
    def setUp(self):
        import os
        import tempfile

        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir.name, "test.db")
        database.init_db()

    def tearDown(self):
        database.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_three_successes_then_blocked(self):
        user = database.create_user("quota@example.com", "hash")
        allowed, remaining = database.check_summary_quota(user["id"])
        self.assertTrue(allowed)
        self.assertEqual(remaining, 3)

        self.assertEqual(database.increment_summary(user["id"]), 2)
        self.assertEqual(database.increment_summary(user["id"]), 1)
        self.assertEqual(database.increment_summary(user["id"]), 0)

        allowed, remaining = database.check_summary_quota(user["id"])
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)

    def test_unknown_user_is_blocked(self):
        allowed, remaining = database.check_summary_quota(999999)
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)


if __name__ == "__main__":
    unittest.main()
