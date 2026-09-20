import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class LabSanityTests(unittest.TestCase):
    def test_policy_exists(self):
        self.assertTrue((ROOT / ".watchdog" / "policy.json").is_file())

    def test_active_task_exists(self):
        self.assertTrue((ROOT / ".watchdog" / "active_task.json").is_file())

    def test_hooks_exist(self):
        self.assertTrue((ROOT / ".githooks" / "pre-commit").is_file())
        self.assertTrue((ROOT / ".githooks" / "pre-push").is_file())

if __name__ == "__main__":
    unittest.main()
