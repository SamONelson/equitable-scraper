import csv
import os
import tempfile
import unittest
from unittest import mock

from policy import Policy, PolicyValueCodes, write_policies_csv


class PolicyCsvTests(unittest.TestCase):
    def make_policy(self, key, cash_value):
        policy = Policy()
        policy.key = key
        policy.cashValue = cash_value
        return policy

    def test_header_matches_attributes(self):
        policy = self.make_policy("A", "100")
        self.assertEqual(policy.header_csv(), policy.get_object_attributes())
        self.assertIn('key', policy.header_csv())
        self.assertIn('cashValue', policy.header_csv())

    def test_data_csv_is_all_strings(self):
        policy = self.make_policy("A", "100")
        self.assertTrue(all(isinstance(value, str) for value in policy.data_csv()))

    def test_write_policies_csv_writes_header_and_every_policy(self):
        policies = [self.make_policy("A", "100"), self.make_policy("B", "200")]
        with tempfile.TemporaryDirectory() as folder:
            path = write_policies_csv(policies, "test.csv", output_folder=folder)
            with open(path, newline="") as f:
                rows = list(csv.reader(f))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], policies[0].header_csv())
        key_index = rows[0].index('key')
        self.assertEqual([row[key_index] for row in rows[1:]], ["A", "B"])

    def test_write_policies_csv_creates_output_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            target = os.path.join(folder, "nested")
            path = write_policies_csv([self.make_policy("A", "100")], "test.csv", output_folder=target)
            self.assertTrue(os.path.isfile(path))

    def test_write_policies_csv_uses_environment_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.dict(os.environ, {'OUTPUT_FOLDER': folder}):
                path = write_policies_csv([self.make_policy("A", "100")], "test.csv")
            self.assertEqual(path, os.path.join(folder, "test.csv"))

    def test_write_policies_csv_with_no_policies(self):
        with tempfile.TemporaryDirectory() as folder:
            path = write_policies_csv([], "test.csv", output_folder=folder)
            with open(path, newline="") as f:
                self.assertEqual(list(csv.reader(f)), [])


class PolicyValueCodesTests(unittest.TestCase):
    def test_expected_labels_are_present(self):
        self.assertEqual(PolicyValueCodes.CV_PUA, "Cash Value of Paid Up Additions")
        self.assertEqual(PolicyValueCodes.TOTAL_ACB, "Total Adjusted Cost Basis Amount")


if __name__ == '__main__':
    unittest.main()
