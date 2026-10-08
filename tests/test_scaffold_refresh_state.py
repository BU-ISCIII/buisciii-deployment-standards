"""Exercise historical baseline verification using an isolated standards Git repo."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RefreshStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.standard = self.directory / "standard"
        self.standard.mkdir()
        for name in ("scripts", "scaffold", "lib"):
            shutil.copytree(ROOT / name, self.standard / name)
        self.git("init", "-q")
        self.git("config", "user.name", "Scaffold test")
        self.git("config", "user.email", "scaffold@example.invalid")
        self.git("add", ".")
        self.git("commit", "-qm", "Baseline")
        self.baseline = self.git("rev-parse", "HEAD").stdout.strip()
        self.target = self.directory / "application"
        self.cli("init", "--config", str(self.standard / "scaffold/project.json.example"))
        self.installer = self.target / "container_install.sh"
        self.state_path = self.target / ".bu-isciii-deployment/state.json"

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.standard), *args],
            text=True, capture_output=True, check=True,
        )

    def cli(self, command, *args, code=0):
        result = subprocess.run(
            ["python3", str(self.standard / "scripts/scaffold.py"),
             command, str(self.target), *args], text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def state(self):
        return json.loads(self.state_path.read_text())

    def customize(self):
        self.installer.write_text(self.installer.read_text().replace(
            "application_supports_test_data=false", "application_supports_test_data=true",
        ))

    def update_standard(self):
        template = self.standard / "scaffold/templates/common/container_install.sh.tmpl"
        template.write_text(template.read_text() + "\n# New managed behavior\n")
        self.git("add", ".")
        self.git("commit", "-qm", "Update")
        return self.git("rev-parse", "HEAD").stdout.strip()

    def test_refresh_after_standard_update_and_conflict(self):
        self.assertEqual(self.state()["standard_revision"], self.baseline)
        self.customize()
        updated = self.update_standard()
        self.cli("sync", code=2)
        self.assertEqual(self.state()["standard_revision"], self.baseline)
        content = self.installer.read_bytes()
        result = self.cli("refresh-state")
        self.assertIn("refreshed container_install.sh", result.stdout)
        self.assertEqual(self.installer.read_bytes(), content)
        self.assertEqual(self.state()["standard_revision"], self.baseline)
        self.cli("sync")
        self.assertEqual(self.state()["standard_revision"], updated)
        self.assertIn("application_supports_test_data=true", self.installer.read_text())
        self.assertIn("# New managed behavior", self.installer.read_text())
        self.cli("check")

    def test_reject_managed_edit_without_writing_state(self):
        self.customize()
        self.installer.write_text(self.installer.read_text() + "\n# Unsupported edit\n")
        state = self.state_path.read_bytes()
        self.cli("refresh-state", code=1)
        self.assertEqual(self.state_path.read_bytes(), state)

    def test_legacy_state_requires_explicit_revision(self):
        state = self.state()
        del state["standard_revision"]
        self.state_path.write_text(json.dumps(state))
        self.customize()
        self.update_standard()
        self.cli("refresh-state", code=1)
        self.cli("refresh-state", "--baseline-ref", self.baseline)
        self.assertEqual(self.state()["standard_revision"], self.baseline)
        self.cli("sync")

    def test_ref_override_and_unavailable_revision_rejected(self):
        updated = self.update_standard()
        self.cli("refresh-state", "--baseline-ref", updated, code=1)
        self.cli("refresh-state", "--baseline-ref", "missing-revision", code=1)

    def test_unrelated_hashes_and_files_are_not_accepted(self):
        self.customize()
        unrelated = self.target / "Dockerfile"
        unrelated.write_text(unrelated.read_text() + "\n# Local managed edit\n")
        original_hash = self.state()["files"]["Dockerfile"]
        content = unrelated.read_bytes()
        self.cli("refresh-state")
        self.assertEqual(self.state()["files"]["Dockerfile"], original_hash)
        self.assertEqual(unrelated.read_bytes(), content)
        self.cli("sync", code=2)

    def test_missing_block_file_refuses_all_hash_updates(self):
        self.customize()
        self.installer.unlink()
        original = self.state_path.read_bytes()
        self.cli("refresh-state", code=1)
        self.assertEqual(self.state_path.read_bytes(), original)

    def test_clean_legacy_sync_records_revision_and_dirty_sources_do_not(self):
        state = self.state()
        del state["standard_revision"]
        self.state_path.write_text(json.dumps(state))
        self.cli("sync")
        self.assertEqual(self.state()["standard_revision"], self.baseline)
        template = self.standard / "scaffold/templates/common/container_install.sh.tmpl"
        template.write_text(template.read_text() + "\n# Uncommitted change\n")
        self.cli("sync")
        self.assertNotIn("standard_revision", self.state())


if __name__ == "__main__":
    unittest.main()
