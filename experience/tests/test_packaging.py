"""Installer/scanner integration tests; all changes stay in temporary fixtures."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, str(REPO / relative))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


installer = module("experience_installer_test", "tools/install.py")
checker = module("experience_checker_test", "tools/check-suite.py")


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="experience-packaging-")
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.host = self.root / "host"
        self.state = self.root / "state"
        self.skill = self.source / "experience"
        self.skill.mkdir(parents=True)
        self.write(self.skill / "SKILL.md", "工程记忆\n")
        self.write(self.skill / "scripts" / "memory.mjs", "export const readonly = true;\n")

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def write(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as stream:
            stream.write(text)

    def run_install(self, *extra):
        args = ["install.py", "--source", str(self.source), "--host-dir", str(self.host),
                "--state-dir", str(self.state), "--skills", "experience"] + list(extra)
        with patch.object(sys, "argv", args):
            return installer.main()

    def add_development_artifacts(self):
        for name in ("node_modules", ".stryker-tmp", "reports", "coverage", ".quality-venv"):
            self.write(self.skill / name / "nested" / "junk.txt", "开发工具，不应安装\n")
        self.write(self.skill / "__pycache__" / "junk.pyc", "fixture\n")

    def test_manifest_excludes_generated_development_artifacts(self):
        self.add_development_artifacts()
        manifest = installer.build_manifest(str(self.skill))
        self.assertEqual({"SKILL.md", "scripts/memory.mjs"}, set(manifest))
        self.assertEqual([], installer.check_manifest(str(self.skill), manifest))

    def test_install_does_not_copy_dev_trees_and_preserves_chinese(self):
        self.add_development_artifacts()
        self.assertEqual(0, self.run_install())
        target = self.host / "experience"
        self.assertEqual("工程记忆\n", (target / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual({"SKILL.md", "scripts"}, {item.name for item in target.iterdir()})
        self.assertEqual(0, self.run_install("--verify-only"))
        state = json.loads((self.state / "install-state.json").read_text(encoding="utf-8"))
        self.assertEqual({"SKILL.md", "scripts/memory.mjs"}, set(state["experience"]["files"]))

    def test_dry_run_keeps_existing_installation(self):
        target = self.host / "experience"
        self.write(target / "old.md", "原内容\n")
        self.assertEqual(0, self.run_install("--dry-run"))
        self.assertEqual({"old.md"}, {item.name for item in target.iterdir()})
        self.assertEqual("原内容\n", (target / "old.md").read_text(encoding="utf-8"))
        self.assertFalse((self.state / "install-state.json").exists())
        self.assertFalse(any(self.host.glob(".install-stage-*")))

    def test_failed_installed_readback_restores_existing_installation(self):
        target = self.host / "experience"
        self.write(target / "old.md", "恢复依据\n")
        original = installer.check_manifest

        def fail_target(base, manifest):
            if Path(base) == target:
                return ["injected readback mismatch"]
            return original(base, manifest)

        with patch.object(installer, "check_manifest", side_effect=fail_target):
            self.assertEqual(1, self.run_install())
        self.assertEqual({"old.md"}, {item.name for item in target.iterdir()})
        self.assertEqual("恢复依据\n", (target / "old.md").read_text(encoding="utf-8"))

    def test_scanner_excludes_generated_artifacts_but_reads_mjs(self):
        self.add_development_artifacts()
        bad = self.skill / "node_modules" / "bad.md"
        bad.write_bytes(bytes([255, 254]))
        with patch.object(checker, "ROOT", str(self.source)), patch.object(checker, "errors", []):
            checker.check_encoding()
            self.assertEqual([], checker.errors)
            (self.skill / "scripts" / "invalid.mjs").write_bytes(bytes([255, 254]))
            checker.check_encoding()
            self.assertEqual(1, len(checker.errors))
            self.assertIn("invalid.mjs", checker.errors[0])

    def test_source_walk_still_checks_distributed_references(self):
        self.add_development_artifacts()
        self.write(self.skill / "references" / "knowledge.md", "有效来源\n")
        with patch.object(checker, "ROOT", str(self.source)), patch.object(checker, "SKILLS", ["experience"]):
            paths = {Path(item).relative_to(self.skill).as_posix() for item in checker.iter_skill_md()}
        self.assertEqual({"SKILL.md", "references/knowledge.md"}, paths)


if __name__ == "__main__":
    unittest.main()
