import unittest
from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def load_manifest(file_name):
    return yaml.safe_load((REPOSITORY_ROOT / file_name).read_text(encoding="utf-8"))


class TestPreCommitHooksManifest(unittest.TestCase):
    def test_hooks_run_deply_commands_on_the_whole_project(self):
        hooks_by_id = {hook["id"]: hook for hook in load_manifest(".pre-commit-hooks.yaml")}
        expected_entries = {"deply": "deply analyze", "deply-validate": "deply validate"}

        self.assertEqual(set(expected_entries), set(hooks_by_id))
        for hook_id, expected_entry in expected_entries.items():
            hook = hooks_by_id[hook_id]
            self.assertTrue(hook["name"])
            self.assertEqual("python", hook["language"])
            self.assertIs(False, hook["pass_filenames"])
            self.assertTrue(hook["entry"].startswith(expected_entry))


class TestGitHubActionManifest(unittest.TestCase):
    def setUp(self):
        self.action = load_manifest("action.yml")

    def test_action_is_composite_with_documented_inputs(self):
        self.assertEqual("composite", self.action["runs"]["using"])
        self.assertEqual(
            {"config", "args", "python-version", "baseline", "report-format"},
            set(self.action["inputs"]),
        )

    def test_run_steps_declare_shell_and_install_action_ref(self):
        run_steps = [step for step in self.action["runs"]["steps"] if "run" in step]

        self.assertTrue(run_steps)
        self.assertTrue(all("shell" in step for step in run_steps))
        self.assertIn("github.action_path", run_steps[0]["run"])
        self.assertIn("pip install", run_steps[0]["run"])


if __name__ == "__main__":
    unittest.main()
