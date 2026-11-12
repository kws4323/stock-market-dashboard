import json
import unittest
from datetime import datetime, timezone
from collect import epoch_seconds, finite

class SerializationTests(unittest.TestCase):
    def test_datetime_metadata_serializes_as_seconds(self):
        result = epoch_seconds(datetime(2026, 1, 1, tzinfo=timezone.utc), 0)
        self.assertEqual(json.loads(json.dumps({"time": result}))["time"], 1767225600)

    def test_numeric_and_missing_metadata(self):
        self.assertEqual(epoch_seconds(1767225600, 0), 1767225600)
        self.assertEqual(epoch_seconds(None, 42), 42)
        self.assertEqual(epoch_seconds(float("nan"), 42), 42)

    def test_nonfinite_prices_are_rejected(self):
        self.assertIsNone(finite(float("nan")))
        self.assertIsNone(finite(float("inf")))

if __name__ == "__main__":
    unittest.main()
