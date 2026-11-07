"""Stage failure contracts for the existing installer and suite scanner."""
import contextlib
import importlib.util
import io
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, str(REPO / relative))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = load_module("stage_installer", "tools/install.py")
checker = load_module("stage_checker", "tools/check-suite.py")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


class InstallStages(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="experience-stage-contract-")
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.host = self.root / "host"
        self.state = self.root / "state"
        for name in ("experience", "pm"):
            write(self.source / name / "SKILL.md", "new " + name + "\n")
            write(self.host / name / "SKILL.md", "old " + name + "\n")
        self.state_before = {"unrelated": {"note": "保留其他安装记录"}}
        write(self.state / "install-state.json", json.dumps(self.state_before, ensure_ascii=False))

    def tearDown(self):
        self.temp.cleanup()

    def run_install(self, *extra, skills=("experience", "pm")):
        argv = ["install.py", "--source", str(self.source), "--host-dir", str(self.host),
                "--state-dir", str(self.state), "--skills", *skills, *extra]
        output = io.StringIO()
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
            result = installer.main()
        self.output = output.getvalue()
        return result

    def assert_original_installations(self):
        for name in ("experience", "pm"):
            self.assertEqual("old " + name + "\n", (self.host / name / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual(self.state_before, json.loads((self.state / "install-state.json").read_text(encoding="utf-8")))
        self.assertFalse(any(self.host.glob(".install-stage-*")))

    def test_verify_unknown_skill_is_read_only_failure(self):
        self.assertEqual(1, self.run_install("--verify-only"))
        self.assert_original_installations()

    def test_source_missing_after_first_stage_preserves_installs(self):
        self.assertEqual(1, self.run_install(skills=("experience", "missing")))
        self.assert_original_installations()

    def test_staging_copy_failure_preserves_installs(self):
        with patch.object(installer.shutil, "copytree", side_effect=OSError("injected copy failure")):
            self.assertEqual(1, self.run_install())
        self.assert_original_installations()

    def test_staging_readback_failure_preserves_installs(self):
        with patch.object(installer, "check_manifest", return_value=["injected staged mismatch"]):
            self.assertEqual(1, self.run_install())
        self.assert_original_installations()

    def test_second_backup_failure_restores_first_backup(self):
        original_move = installer.shutil.move

        def fail_second_backup(source, destination):
            if Path(source) == self.host / "pm":
                raise OSError("injected backup failure")
            return original_move(source, destination)

        with patch.object(installer.shutil, "move", side_effect=fail_second_backup):
            self.assertEqual(1, self.run_install())
        self.assert_original_installations()

    def test_second_activation_failure_removes_new_first_and_restores_both(self):
        original_move = installer.shutil.move

        def fail_second_activation(source, destination):
            candidate = Path(source)
            if candidate.name == "pm" and candidate.parent.name.startswith(".install-stage-"):
                raise OSError("injected activation failure")
            return original_move(source, destination)

        with patch.object(installer.shutil, "move", side_effect=fail_second_activation):
            self.assertEqual(1, self.run_install())
        self.assert_original_installations()

    def test_state_save_failure_rolls_back_installed_files(self):
        with patch.object(installer, "save_state", side_effect=OSError("injected state failure")):
            self.assertEqual(1, self.run_install())
        self.assert_original_installations()
        self.assertIn("已回滚到安装前状态", self.output)
        self.assertNotIn("恢复不完整", self.output)

    def test_success_preserves_unrelated_state_and_cleans_transient_directories(self):
        self.assertEqual(0, self.run_install())
        for name in ("experience", "pm"):
            self.assertEqual("new " + name + "\n", (self.host / name / "SKILL.md").read_text(encoding="utf-8"))
        state = json.loads((self.state / "install-state.json").read_text(encoding="utf-8"))
        self.assertEqual(self.state_before["unrelated"], state["unrelated"])
        self.assertEqual({"SKILL.md"}, set(state["experience"]["files"]))
        self.assertEqual(64, len(state["experience"]["sha256_root"]))
        self.assertEqual(0, self.run_install("--verify-only"))
        self.assertFalse(any(self.host.glob(".install-stage-*")))
        self.assertFalse(any(self.state.glob("backup-*")))

    def test_verify_reports_drift_after_success(self):
        self.assertEqual(0, self.run_install())
        write(self.host / "experience" / "SKILL.md", "changed after install\n")
        self.assertEqual(1, self.run_install("--verify-only"))

    def test_install_without_existing_skill_and_default_state_path(self):
        fresh_host = self.root / "fresh"
        argv = ["install.py", "--source", str(self.source), "--host-dir", str(fresh_host),
                "--skills", "experience"]
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, installer.main())
        self.assertEqual("new experience\n", (fresh_host / "experience" / "SKILL.md").read_text(encoding="utf-8"))
        self.assertTrue((fresh_host / ".install-state" / "install-state.json").is_file())

    def test_load_state_only_missing_returns_empty(self):
        self.assertEqual({}, installer.load_state(str(self.root / "absent")))
        write(self.state / "install-state.json", "{not json")
        with self.assertRaises(json.JSONDecodeError):
            installer.load_state(str(self.state))

    def test_state_write_flush_and_close_failures_preserve_original_bytes(self):
        import builtins
        real_open = builtins.open
        real_fdopen = installer.os.fdopen
        state_path = self.state / "install-state.json"
        original_bytes = state_path.read_bytes()

        class FaultyWriter:
            def __init__(self, stream, phase, faults):
                self.stream = stream
                self.phase = phase
                self.faults = faults

            def __enter__(self):
                return self

            def __getattr__(self, name):
                return getattr(self.stream, name)

            def write(self, text):
                result = self.stream.write(text)
                if self.phase == "write":
                    self.stream.flush()
                    self.faults.append(self.phase)
                    raise OSError("injected partial write")
                return result

            def flush(self):
                if self.phase == "flush":
                    self.faults.append(self.phase)
                    raise OSError("injected flush failure")
                return self.stream.flush()

            def __exit__(self, kind, value, traceback):
                try:
                    if kind is None:
                        self.flush()
                finally:
                    self.stream.close()
                if kind is None and self.phase == "close":
                    self.faults.append(self.phase)
                    raise OSError("injected close failure")
                return False

        for phase in ("write", "flush", "close"):
            with self.subTest(phase=phase):
                state_path.write_bytes(original_bytes)
                for name in ("experience", "pm"):
                    write(self.host / name / "SKILL.md", "old " + name + "\n")
                faults = []

                def wrapped_open(file, mode="r", *args, **kwargs):
                    stream = real_open(file, mode, *args, **kwargs)
                    if "w" in mode and Path(file).parent == self.state:
                        return FaultyWriter(stream, phase, faults)
                    return stream

                def wrapped_fdopen(fd, mode="r", *args, **kwargs):
                    stream = real_fdopen(fd, mode, *args, **kwargs)
                    return FaultyWriter(stream, phase, faults) if "w" in mode else stream

                with patch.object(builtins, "open", side_effect=wrapped_open):
                    with patch.object(installer.os, "fdopen", side_effect=wrapped_fdopen):
                        self.assertEqual(1, self.run_install())
                self.assertTrue(faults)
                self.assertEqual(original_bytes, state_path.read_bytes())
                self.assert_original_installations()
                self.assertFalse(any(self.state.glob(".install-state-*.tmp")))

    def test_state_replace_failure_preserves_existing_state_and_installations(self):
        original_bytes = (self.state / "install-state.json").read_bytes()
        with patch.object(installer.os, "replace", side_effect=OSError("injected replace failure")):
            self.assertEqual(1, self.run_install())
        self.assertEqual(original_bytes, (self.state / "install-state.json").read_bytes())
        self.assert_original_installations()

    def test_invalid_existing_state_fails_without_replacement(self):
        for value in ("{broken", "[]"):
            with self.subTest(value=value):
                for name in ("experience", "pm"):
                    write(self.host / name / "SKILL.md", "old " + name + "\n")
                write(self.state / "install-state.json", value)
                with patch.object(installer, "_stage_skills", wraps=installer._stage_skills) as stage:
                    self.assertEqual(1, self.run_install())
                stage.assert_not_called()
                self.assertEqual(value, (self.state / "install-state.json").read_text(encoding="utf-8"))
                self.assertEqual("old experience\n", (self.host / "experience" / "SKILL.md").read_text(encoding="utf-8"))

    def test_locked_new_target_preserves_backup_without_nested_restore(self):
        real_check = installer.check_manifest
        real_remove = installer.shutil.rmtree
        target = self.host / "experience"

        def check(base, manifest):
            return ["readback failure"] if Path(base) == target else real_check(base, manifest)

        def remove(path, *args, **kwargs):
            if Path(path) == target:
                if kwargs.get("ignore_errors"):
                    return None
                raise PermissionError("target is locked")
            return real_remove(path, *args, **kwargs)

        with patch.object(installer, "check_manifest", side_effect=check):
            with patch.object(installer.shutil, "rmtree", side_effect=remove):
                self.assertEqual(1, self.run_install())
        self.assertIn("恢复不完整", self.output)
        self.assertNotIn("已回滚到安装前状态", self.output)
        self.assertFalse((target / "experience").exists())
        self.assertIn("恢复目标仍存在", self.output)
        backups = list(self.state.glob("backup-*/experience/SKILL.md"))
        self.assertEqual(1, len(backups))
        self.assertEqual("old experience\n", backups[0].read_text(encoding="utf-8"))

    def test_restore_copy_failure_keeps_backup_and_reports_partial_recovery(self):
        real_copy = installer.shutil.copytree
        real_check = installer.check_manifest
        target = self.host / "experience"

        def copy(source, destination, *args, **kwargs):
            path = Path(source)
            if path.name == "experience" and path.parent.name.startswith("backup-"):
                raise OSError("injected restore failure")
            return real_copy(source, destination, *args, **kwargs)

        def check(base, manifest):
            return ["readback failure"] if Path(base) == target else real_check(base, manifest)

        with patch.object(installer.shutil, "copytree", side_effect=copy):
            with patch.object(installer, "check_manifest", side_effect=check):
                self.assertEqual(1, self.run_install())
        self.assertIn("恢复不完整", self.output)
        self.assertNotIn("已回滚到安装前状态", self.output)
        self.assertEqual(1, len(list(self.state.glob("backup-*/experience/SKILL.md"))))

    def test_empty_and_development_only_sources_are_not_installable(self):
        (self.source / "experience" / "SKILL.md").unlink()
        self.assertEqual(1, self.run_install(skills=("experience",)))
        write(self.source / "experience" / "node_modules" / "dependency.txt", "development only\n")
        self.assertEqual(1, self.run_install(skills=("experience",)))
        self.assert_original_installations()

    def test_skill_entry_must_be_a_regular_file(self):
        entry = self.source / "experience" / "SKILL.md"
        entry.unlink()
        entry.mkdir()
        write(entry / "nested.txt", "not a skill entry")
        self.assertEqual(1, self.run_install(skills=("experience",)))
        self.assert_original_installations()

    def test_manifest_validation_rejects_empty_missing_and_invalid_records(self):
        absent = self.root / "absent"
        empty = self.root / "empty"
        empty.mkdir()
        self.assertTrue(installer.check_manifest(str(absent), {}))
        self.assertTrue(installer.check_manifest(str(empty), {}))
        self.assertTrue(installer.check_manifest(str(self.host / "experience"), None))
        write(self.state / "install-state.json", json.dumps({"missing": {"files": {}}}))
        self.assertEqual(1, self.run_install("--verify-only", skills=("missing",)))

    def test_verify_fails_if_installed_directory_was_deleted(self):
        self.assertEqual(0, self.run_install())
        state_bytes = (self.state / "install-state.json").read_bytes()
        installer.shutil.rmtree(str(self.host / "experience"))
        self.assertEqual(1, self.run_install("--verify-only"))
        self.assertEqual(state_bytes, (self.state / "install-state.json").read_bytes())

    def test_source_skill_symlink_is_not_a_regular_entry(self):
        entry = self.source / "experience" / "SKILL.md"
        entry.unlink()
        other = self.root / "outside-skill.md"
        write(other, "outside source\n")
        try:
            installer.os.symlink(str(other), str(entry))
        except (OSError, NotImplementedError) as error:
            self.skipTest("OS does not allow fixture symlinks: " + str(error))
        self.assertEqual(1, self.run_install(skills=("experience",)))
        self.assert_original_installations()

    def test_restore_hash_mismatch_keeps_backup_and_never_reports_success(self):
        real_copy = installer.shutil.copytree
        target = self.host / "experience"

        def copy(source, destination, *args, **kwargs):
            result = real_copy(source, destination, *args, **kwargs)
            source_path = Path(source)
            if source_path.name == "experience" and source_path.parent.name.startswith("backup-"):
                write(Path(destination) / "SKILL.md", "corrupted restore\n")
            return result

        with patch.object(installer.shutil, "copytree", side_effect=copy):
            with patch.object(installer, "save_state", side_effect=OSError("trigger rollback")):
                self.assertEqual(1, self.run_install())
        self.assertIn("恢复不完整", self.output)
        self.assertNotIn("已回滚到安装前状态", self.output)
        backups = list(self.state.glob("backup-*/experience/SKILL.md"))
        self.assertEqual(1, len(backups))
        self.assertEqual("old experience\n", backups[0].read_text(encoding="utf-8"))
        self.assertEqual("corrupted restore\n", (target / "SKILL.md").read_text(encoding="utf-8"))
        self.assertIn("恢复读回不一致", self.output)

    def test_manifest_record_rejects_bad_hashes_and_unsafe_names_before_readback(self):
        target = self.host / "experience"
        digest = hashlib.sha256((target / "SKILL.md").read_bytes()).hexdigest()
        for value in (None, 7, [], {}, "f" * 63, "f" * 65, "x" * 64, "F" * 64):
            with self.subTest(hash=value):
                errors = installer.check_manifest(str(target), {"SKILL.md": value})
                self.assertTrue(errors)
                self.assertIn("安装清单", errors[0])
        for name in ("../other.md", "/absolute.md", "sub/../other.md", "C:other.md", "sub\\other.md"):
            with self.subTest(name=name):
                errors = installer.check_manifest(str(target), {"SKILL.md": digest, name: digest})
                self.assertTrue(errors)
                self.assertIn("安装清单", errors[0])
        errors = installer.check_manifest(str(target), {"SKILL.md": digest, "missing.md": "0" * 64})
        self.assertEqual(["缺失: missing.md"], errors)

    def test_ignored_file_does_not_stop_manifest_processing(self):
        target = self.host / "experience"
        write(target / ".DS_Store", "ignored\n")
        expected = {"SKILL.md": hashlib.sha256((target / "SKILL.md").read_bytes()).hexdigest()}

        def walk(_root):
            return iter([(str(target), [], [".DS_Store", "SKILL.md"])])

        with patch.object(installer.os, "walk", side_effect=walk):
            self.assertEqual(expected, installer.build_manifest(str(target)))
            self.assertEqual([], installer.check_manifest(str(target), expected))

    def test_manifest_root_digest_is_canonical_for_multifile_install(self):
        write(self.source / "experience" / "z.md", "z\n")
        write(self.source / "experience" / "a.md", "a\n")
        write(self.source / "experience" / "说明.md", "中文\n")
        self.assertEqual(0, self.run_install())
        state = json.loads((self.state / "install-state.json").read_text(encoding="utf-8"))
        expected = hashlib.sha256(json.dumps(state["experience"]["files"], sort_keys=True).encode("utf-8")).hexdigest()
        self.assertEqual(expected, state["experience"]["sha256_root"])
        self.assertEqual(0, self.run_install("--verify-only"))
        self.assertIn("VERIFY OK (2 skills)", self.output)

    def test_failure_diagnostics_identify_the_failed_stage(self):
        source_entry = self.source / "experience" / "SKILL.md"
        source_entry.unlink()
        self.assertEqual(1, self.run_install())
        self.assertIn("源 skill 无效 experience", self.output)
        write(source_entry, "new experience\n")
        with patch.object(installer, "check_manifest", return_value=["staged fixture mismatch"]):
            self.assertEqual(1, self.run_install())
        self.assertIn("暂存校验失败 experience", self.output)
        original = installer.check_manifest

        def check(base, manifest):
            return ["installed fixture mismatch"] if Path(base) == self.host / "experience" else original(base, manifest)

        with patch.object(installer, "check_manifest", side_effect=check):
            self.assertEqual(1, self.run_install())
        self.assertIn("读回校验失败 experience", self.output)
        self.assert_original_installations()

    def test_manifest_additional_file_is_reported_without_exception(self):
        target = self.host / "experience"
        manifest = installer.build_manifest(str(target))
        write(target / "unexpected.md", "extra\n")
        self.assertEqual(["多出文件: unexpected.md"], installer.check_manifest(str(target), manifest))

    def test_invalid_skill_entry_has_actionable_diagnostic(self):
        entry = self.source / "experience" / "SKILL.md"
        entry.unlink()
        entry.mkdir()
        self.assertEqual(1, self.run_install(skills=("experience",)))
        self.assertIn("SKILL.md 应为普通文件", self.output)

    def test_invalid_built_manifest_is_rejected_before_copying(self):
        original = installer.build_manifest

        def manifest(path):
            return {} if Path(path) == self.source / "experience" else original(path)

        with patch.object(installer, "build_manifest", side_effect=manifest):
            self.assertEqual(1, self.run_install())
        self.assertIn("源安装清单为空或无效: experience", self.output)
        self.assert_original_installations()

    def test_missing_restore_backup_reports_path(self):
        absent_host = self.root / "absent-host"
        absent_backup = self.root / "absent-backup"
        with self.assertRaisesRegex(RuntimeError, "恢复备份不存在"):
            installer._restore_backup(str(absent_host), str(absent_backup), "experience")

    def test_preexisting_backup_directory_cannot_be_reused(self):
        backup = self.root / "existing-backup"
        backup.mkdir()
        write(backup / "sentinel.md", "must survive\n")
        with self.assertRaises(FileExistsError):
            installer._backup_skills(str(self.host), str(backup), ["experience"], [])
        self.assertEqual("must survive\n", (backup / "sentinel.md").read_text(encoding="utf-8"))
        self.assertEqual("old experience\n", (self.host / "experience" / "SKILL.md").read_text(encoding="utf-8"))

    def test_required_cli_arguments_fail_with_argparse_diagnostic(self):
        cases = (["--host-dir", str(self.host)], ["--source", str(self.source)])
        for arguments in cases:
            with self.subTest(arguments=arguments):
                error_output = io.StringIO()
                with patch.object(sys, "argv", ["install.py", *arguments]):
                    with contextlib.redirect_stderr(error_output), self.assertRaises(SystemExit) as failure:
                        installer.main()
                self.assertEqual(2, failure.exception.code)
                self.assertIn("required", error_output.getvalue())

    def test_recovery_log_distinguishes_backups_from_prebackup_failure(self):
        with patch.object(installer, "save_state", side_effect=OSError("rollback after backup")):
            self.assertEqual(1, self.run_install())
        self.assertIn("恢复备份保留在:", self.output)
        with patch.object(installer.shutil, "copytree", side_effect=OSError("before backup")):
            self.assertEqual(1, self.run_install())
        self.assertNotIn("恢复备份保留在:", self.output)

    def test_success_messages_and_state_preserve_utf8_content(self):
        self.assertEqual(0, self.run_install())
        self.assertIn("backup experience\n", self.output)
        self.assertIn("installed experience (readback ok)\n", self.output)
        state_text = (self.state / "install-state.json").read_text(encoding="utf-8")
        self.assertIn("保留其他安装记录", state_text)
        self.assertEqual(self.state_before["unrelated"], json.loads(state_text)["unrelated"])

    def test_reparse_attribute_rejects_regular_mode_independently(self):
        from types import SimpleNamespace
        entry = self.source / "experience" / "SKILL.md"
        real_lstat = installer.os.lstat
        flag = getattr(installer.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)

        def info(path):
            if Path(path) == entry:
                return SimpleNamespace(st_mode=installer.stat.S_IFREG, st_file_attributes=flag | 32)
            return real_lstat(path)

        with patch.object(installer.os, "lstat", side_effect=info):
            errors = installer._skill_directory_errors(str(self.source / "experience"))
        self.assertTrue(errors)
        self.assertIn("SKILL.md 应为普通文件", errors[0])

    def test_other_windows_attribute_does_not_mark_regular_file_as_reparse(self):
        from types import SimpleNamespace
        entry = self.source / "experience" / "SKILL.md"
        real_lstat = installer.os.lstat

        def info(path):
            if Path(path) == entry:
                return SimpleNamespace(st_mode=installer.stat.S_IFREG, st_file_attributes=2048 | 32)
            return real_lstat(path)

        with patch.object(installer.os, "lstat", side_effect=info):
            self.assertEqual([], installer._skill_directory_errors(str(self.source / "experience")))

    def test_verify_continues_after_missing_record(self):
        self.assertEqual(0, self.run_install(skills=("pm",)))
        write(self.host / "pm" / "SKILL.md", "changed pm\n")
        self.assertEqual(1, self.run_install("--verify-only", skills=("missing", "pm")))
        self.assertIn("missing: 无安装记录", self.output)
        self.assertIn("pm: 哈希不符", self.output)

    def test_manifest_wrong_shape_and_digest_order_are_rejected(self):
        target = self.host / "experience"
        for manifest in (["SKILL.md"], {"SKILL.md"}, 5):
            with self.subTest(manifest=manifest):
                self.assertTrue(installer.check_manifest(str(target), manifest))
        for name in (None, 5, ("x",)):
            with self.subTest(name=name):
                self.assertTrue(installer.check_manifest(str(target), {"SKILL.md": "0" * 64, name: "0" * 64}))
        for digest in ("0" * 64, "f" * 64):
            with self.subTest(digest=digest):
                self.assertEqual(["哈希不符: SKILL.md"], installer.check_manifest(str(target), {"SKILL.md": digest}))

    def test_state_readback_mismatch_preserves_old_record(self):
        old = (self.state / "install-state.json").read_bytes()
        real_load = installer.json.load

        def load(handle):
            if Path(handle.name).suffix == ".tmp":
                return {"unexpected": "corruption"}
            return real_load(handle)

        with patch.object(installer.json, "load", side_effect=load):
            with self.assertRaisesRegex(RuntimeError, "安装记录暂存读回不一致"):
                installer.save_state(str(self.state), {"new": "data"})
        self.assertEqual(old, (self.state / "install-state.json").read_bytes())
        self.assertFalse(any(self.state.glob(".install-state-*.tmp")))

    def test_state_json_keeps_existing_two_space_representation(self):
        value = {"中文": {"nested": 1}}
        installer.save_state(str(self.state), value)
        self.assertEqual(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                         (self.state / "install-state.json").read_text(encoding="utf-8"))

    def test_cleanup_failure_does_not_mask_successful_install(self):
        real_remove = installer.shutil.rmtree

        def remove(path, *args, **kwargs):
            if Path(path).name.startswith(".install-stage-") and not kwargs.get("ignore_errors"):
                raise PermissionError("injected cleanup denial")
            return real_remove(path, *args, **kwargs)

        with patch.object(installer.shutil, "rmtree", side_effect=remove):
            self.assertEqual(0, self.run_install())
        self.assertEqual(0, self.run_install("--verify-only"))

    def test_failure_previews_retain_first_three_diagnostics(self):
        failures = ["first", "second", "third", "fourth"]
        with patch.object(installer, "check_manifest", return_value=failures):
            self.assertEqual(1, self.run_install())
        self.assertIn("['first', 'second', 'third']", self.output)
        self.assertNotIn("fourth", self.output)
        original = installer.check_manifest

        def check(base, manifest):
            return failures if Path(base) == self.host / "experience" else original(base, manifest)

        with patch.object(installer, "check_manifest", side_effect=check):
            self.assertEqual(1, self.run_install())
        self.assertIn("['first', 'second', 'third']", self.output)
        self.assertNotIn("fourth", self.output)

    def test_missing_platform_attributes_preserve_regular_file_behavior(self):
        from types import SimpleNamespace
        entry = self.source / "experience" / "SKILL.md"
        original = installer.os.lstat

        def info(path):
            return SimpleNamespace(st_mode=installer.stat.S_IFREG) if Path(path) == entry else original(path)

        with patch.object(installer.os, "lstat", side_effect=info):
            self.assertEqual([], installer._skill_directory_errors(str(self.source / "experience")))

    def test_missing_platform_constant_preserves_regular_file_behavior(self):
        from types import SimpleNamespace
        entry = self.source / "experience" / "SKILL.md"
        original = installer.os.lstat
        platform = SimpleNamespace(S_ISREG=installer.stat.S_ISREG)

        def info(path):
            return SimpleNamespace(st_mode=0o100000, st_file_attributes=32) if Path(path) == entry else original(path)

        with patch.object(installer.os, "lstat", side_effect=info):
            with patch.object(installer, "stat", platform):
                self.assertEqual([], installer._skill_directory_errors(str(self.source / "experience")))


class ScriptChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="experience-script-contract-")
        self.root = Path(self.temp.name)
        write(self.root / "LICENSE", "license\n")
        write(self.root / "systematic-debugging" / "LICENSE", "license\n")
        write(self.root / "experience" / "run.sh", "true\n")
        write(self.root / "experience" / "agents" / "openai.yaml", "interface:\npolicy:\n")
        self.changes = contextlib.ExitStack()
        self.changes.enter_context(patch.object(checker, "ROOT", str(self.root)))
        self.changes.enter_context(patch.object(checker, "SKILLS", ["experience"]))
        self.changes.enter_context(patch.object(checker, "errors", []))
        self.changes.enter_context(patch.object(checker, "warnings", []))
        self.changes.enter_context(patch.object(checker.shutil, "which", return_value=str(self.root / "bin" / "bash.exe")))

    def tearDown(self):
        self.changes.close()
        self.temp.cleanup()

    @staticmethod
    def responses(mode="100755", shell_return=0):
        def run(args, **kwargs):
            if args[0] == "git":
                return subprocess.CompletedProcess(args, 0, mode + " abc 0\texperience/run.sh\n", "")
            return subprocess.CompletedProcess(args, shell_return, b"", b"syntax fixture")
        return run

    def test_valid_script_mode_and_yaml_pass(self):
        with patch.object(checker.subprocess, "run", side_effect=self.responses()):
            checker.check_license_and_scripts()
        self.assertEqual([], checker.errors)
        self.assertEqual([], checker.warnings)

    def test_bad_syntax_mode_and_yaml_are_reported(self):
        write(self.root / "experience" / "agents" / "openai.yaml", "interface:\n")
        with patch.object(checker.subprocess, "run", side_effect=self.responses("100644", 1)):
            checker.check_license_and_scripts()
        self.assertEqual(3, len(checker.errors))
        self.assertTrue(any("bash 语法错误" in error for error in checker.errors))
        self.assertTrue(any("缺执行位" in error for error in checker.errors))
        self.assertTrue(any("openai.yaml 结构异常" in error for error in checker.errors))

    def test_missing_tools_warn_for_shell_without_inventing_mode_failure(self):
        with patch.object(checker.subprocess, "run", side_effect=FileNotFoundError("fixture missing")):
            checker.check_license_and_scripts()
        self.assertEqual([], checker.errors)
        self.assertEqual(1, len(checker.warnings))

    def test_missing_licenses_are_independent_errors(self):
        (self.root / "LICENSE").unlink()
        (self.root / "systematic-debugging" / "LICENSE").unlink()
        with patch.object(checker.subprocess, "run", side_effect=self.responses()):
            checker.check_license_and_scripts()
        self.assertEqual({"缺根 LICENSE", "缺 systematic-debugging/LICENSE"}, set(checker.errors))

    def test_modes_ignore_malformed_rows_and_preserve_paths_with_spaces(self):
        (self.root / "experience" / "run.sh").rename(self.root / "experience" / "run script.sh")

        def run(args, **kwargs):
            if args[0] == "git":
                output = "invalid row\n100644 abc 0\texperience/run script.sh\n"
                return subprocess.CompletedProcess(args, 0, output, "")
            return subprocess.CompletedProcess(args, 0, b"", b"")

        with patch.object(checker.subprocess, "run", side_effect=run):
            checker.check_license_and_scripts()
        self.assertEqual([".sh 缺执行位(100644): experience/run script.sh"], checker.errors)

    def test_encoding_reports_bom_and_replacement_but_ignores_binary(self):
        (self.root / "experience" / "ignored.bin").write_bytes(bytes([255, 254]))
        (self.root / "experience" / "bom.mjs").write_bytes(bytes([239, 187, 191]) + b"const x = 1;\n")
        (self.root / "experience" / "replacement.md").write_bytes(bytes([239, 191, 189]))
        checker.check_encoding()
        self.assertEqual(2, len(checker.errors))
        self.assertTrue(any("BOM:" in item for item in checker.errors))
        self.assertTrue(any("U+FFFD" in item for item in checker.errors))

    def test_latest_checks_distribution_and_skips_development_trees(self):
        latest = "@" + "latest"
        write(self.root / "experience" / "refs.md", "package" + latest + "\n")
        write(self.root / "experience" / "ignore.bin", "package" + latest + "\n")
        write(self.root / "experience" / "allowed.md", "禁止 package" + latest + "\n")
        write(self.root / "tools" / "check-sample.py", "package" + latest + "\n")
        write(self.root / "experience" / "node_modules" / "dependency.md", "package" + latest + "\n")
        checker.check_latest()
        self.assertEqual(1, len(checker.errors))
        self.assertIn("experience/refs.md:1", checker.errors[0])

    def test_shell_check_uses_resolved_absolute_executable(self):
        executable = str(self.root / "git" / "bash.exe")
        script = str(self.root / "experience" / "run.sh")
        result = subprocess.CompletedProcess([], 0, b"", b"")
        with patch.object(checker.shutil, "which", return_value=executable) as resolve:
            with patch.object(checker.subprocess, "run", return_value=result) as run:
                checker._check_shell_script(script, {})
        resolve.assert_called_once_with("bash")
        run.assert_called_once_with([executable, "-n", script], capture_output=True)
        self.assertEqual([], checker.errors)
        self.assertEqual([], checker.warnings)

    def test_missing_bash_still_checks_tracked_executable_mode(self):
        script = str(self.root / "experience" / "run.sh")
        with patch.object(checker.shutil, "which", return_value=None):
            with patch.object(checker.subprocess, "run") as run:
                checker._check_shell_script(script, {"experience/run.sh": "100644"})
        run.assert_not_called()
        self.assertEqual(1, len(checker.warnings))
        self.assertEqual([".sh 缺执行位(100644): experience/run.sh"], checker.errors)

    def test_git_mode_query_captures_utf8_output(self):
        result = subprocess.CompletedProcess([], 0, "100755 abc 0\texperience/run.sh\n", "")
        with patch.object(checker.subprocess, "run", return_value=result) as run:
            modes = checker._tracked_modes()
        self.assertEqual({"experience/run.sh": "100755"}, modes)
        run.assert_called_once_with(["git", "ls-files", "-s"], cwd=str(self.root),
                                    capture_output=True, text=True, encoding="utf-8")

    def test_negative_shell_exit_is_a_failure(self):
        with patch.object(checker.subprocess, "run", side_effect=self.responses(shell_return=-9)):
            checker.check_license_and_scripts()
        self.assertEqual(1, len(checker.errors))
        self.assertIn("bash 语法错误", checker.errors[0])

    def test_shell_error_preview_has_its_existing_bound(self):
        script = str(self.root / "experience" / "run.sh")
        result = subprocess.CompletedProcess([], 1, b"", b"A" * 200)
        with patch.object(checker.subprocess, "run", return_value=result):
            checker._check_shell_script(script, {})
        self.assertEqual(["bash 语法错误: experience/run.sh: " + "A" * 120], checker.errors)

    def test_ignored_file_does_not_skip_later_distributed_diagnostics(self):
        write(self.root / "ignored.bin", "binary fixture\n")
        write(self.root / "later.md", "package@" + "latest\n")
        (self.root / "invalid.mjs").write_bytes(bytes([255, 254]))

        def walk(_root):
            return iter([(str(self.root), [], ["ignored.bin", "later.md", "invalid.mjs"])])

        with patch.object(checker, "source_walk", side_effect=walk):
            checker.check_latest()
            checker.check_encoding()
        self.assertEqual(2, len(checker.errors))
        self.assertTrue(any("later.md:1" in value for value in checker.errors))
        self.assertTrue(any("invalid.mjs" in value for value in checker.errors))

    def test_executable_mode_above_regular_mode_is_still_rejected(self):
        with patch.object(checker.subprocess, "run", side_effect=self.responses(mode="120000")):
            checker.check_license_and_scripts()
        self.assertEqual([".sh 缺执行位(120000): experience/run.sh"], checker.errors)

    def test_checker_filename_skip_does_not_end_directory_iteration(self):
        write(self.root / "tools" / "check-fixture.py", "@" + "latest\n")
        write(self.root / "tools" / "other.py", "@" + "latest\n")
        rows = [(str(self.root / "tools"), [], ["check-fixture.py", "other.py"])]
        with patch.object(checker, "source_walk", return_value=iter(rows)):
            checker.check_latest()
        self.assertEqual(1, len(checker.errors))
        self.assertIn("tools/other.py", checker.errors[0])

    def test_only_openai_yaml_files_receive_yaml_structure_check(self):
        write(self.root / "experience" / "a.md", "plain documentation\n")
        with patch.object(checker.subprocess, "run", side_effect=self.responses()):
            checker.check_license_and_scripts()
        self.assertEqual([], checker.errors)


if __name__ == "__main__":
    unittest.main()
