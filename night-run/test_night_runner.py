#!/usr/bin/env python3
"""night_runner.pyの純粋関数・フェイルセーフ挙動のユニットテスト。

docker/claude/ghの実プロセスは呼ばず、subprocessやネットワークをモックする。
実行方法: python3 night-run/test_night_runner.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import night_runner  # noqa: E402


class SandboxGuardTest(unittest.TestCase):
    def test_exits_when_env_and_marker_file_both_missing(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NIGHT_RUNNER_SANDBOX", None)
            with mock.patch.object(night_runner, "notify_human"):
                with self.assertRaises(SystemExit) as ctx:
                    night_runner.assert_sandbox_or_exit()
                self.assertEqual(ctx.exception.code, 1)

    def test_exits_when_env_set_but_marker_file_missing(self):
        # 環境変数のspoofだけではガードを通せないことを確認する
        with tempfile.TemporaryDirectory() as tmp:
            missing_marker = os.path.join(tmp, "does-not-exist")
            with mock.patch.dict(os.environ, {"NIGHT_RUNNER_SANDBOX": "1"}), \
                 mock.patch.object(night_runner, "SANDBOX_MARKER_FILE", missing_marker), \
                 mock.patch.object(night_runner, "notify_human"):
                with self.assertRaises(SystemExit) as ctx:
                    night_runner.assert_sandbox_or_exit()
                self.assertEqual(ctx.exception.code, 1)

    def test_passes_when_env_and_marker_file_both_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = os.path.join(tmp, "sandbox-marker")
            open(marker, "w").close()
            with mock.patch.dict(os.environ, {"NIGHT_RUNNER_SANDBOX": "1"}), \
                 mock.patch.object(night_runner, "SANDBOX_MARKER_FILE", marker):
                night_runner.assert_sandbox_or_exit()  # 例外が飛ばなければOK


class StateFileTest(unittest.TestCase):
    def test_save_state_is_atomic_and_adds_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = os.path.join(tmp, "night-run-state.json")
            with mock.patch.object(night_runner, "STATE_FILE", state_path):
                night_runner.save_state({"tasks": []})
                self.assertTrue(os.path.exists(state_path))
                # tmpファイルが残っていないこと(os.replaceで置き換わっている)
                leftovers = [f for f in os.listdir(tmp) if f.endswith(".tmp")]
                self.assertEqual(leftovers, [])
                loaded = night_runner.load_state()
                self.assertIn("last_updated", loaded)


class BackoffTest(unittest.TestCase):
    def test_sequence_matches_design_then_caps(self):
        got = [night_runner.backoff_seconds(a) for a in range(1, 8)]
        self.assertEqual(got, [60, 120, 240, 480, 960, 1800, 1800])


class MainValidationTest(unittest.TestCase):
    def _run_main_with_state(self, state):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = os.path.join(tmp, "night-run-state.json")
            with open(state_path, "w") as f:
                json.dump(state, f)
            marker = os.path.join(tmp, "sandbox-marker")
            open(marker, "w").close()
            with mock.patch.object(night_runner, "STATE_FILE", state_path), \
                 mock.patch.object(night_runner, "REPO_DIR", tmp), \
                 mock.patch.object(night_runner, "SANDBOX_MARKER_FILE", marker), \
                 mock.patch.dict(os.environ, {"NIGHT_RUNNER_SANDBOX": "1"}), \
                 mock.patch.object(night_runner, "notify_human"):
                with self.assertRaises(SystemExit) as ctx:
                    night_runner.main()
                return ctx.exception.code

    def test_missing_hard_limit_exits(self):
        code = self._run_main_with_state({"tasks": []})
        self.assertEqual(code, 1)

    def test_unresolved_depends_on_exits(self):
        state = {
            "hard_limit": "2999-01-01T00:00:00+09:00",
            "deadline": "2999-01-01T00:00:00+09:00",
            "tasks": [{"title": "A", "status": "pending", "depends_on": "B"}],
        }
        code = self._run_main_with_state(state)
        self.assertEqual(code, 1)


class UpdateStateDoneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_path = os.path.join(self.tmp.name, "night-run-state.json")
        patcher_state_file = mock.patch.object(night_runner, "STATE_FILE", self.state_path)
        patcher_state_file.start()
        self.addCleanup(patcher_state_file.stop)
        patcher_alerts = mock.patch.object(
            night_runner, "ALERTS_LOG", os.path.join(self.tmp.name, "alerts.log")
        )
        patcher_alerts.start()
        self.addCleanup(patcher_alerts.stop)
        patcher_diag = mock.patch.object(
            night_runner, "save_diagnostic_branch", return_value="diagnostic/fake-branch"
        )
        patcher_diag.start()
        self.addCleanup(patcher_diag.stop)

        self.task = {"title": "タスクA", "status": "pending", "branch": "night-run/task-a"}
        self.state = {"tasks": [self.task]}

    def test_invalid_json_marks_failed(self):
        night_runner.update_state_done(self.task, self.state, "not-json")
        self.assertEqual(self.task["status"], "failed")

    def test_is_error_marks_failed(self):
        stdout = json.dumps({"is_error": True, "subtype": "error_max_turns", "result": "boom"})
        night_runner.update_state_done(self.task, self.state, stdout)
        self.assertEqual(self.task["status"], "failed")

    def test_missing_structured_output_marks_failed(self):
        stdout = json.dumps({"is_error": False, "result": "plain text, no schema"})
        night_runner.update_state_done(self.task, self.state, stdout)
        self.assertEqual(self.task["status"], "failed")

    def test_self_reported_failed_status_marks_failed(self):
        stdout = json.dumps({
            "is_error": False,
            "structured_output": {
                "status": "failed", "pr_url": None, "branch": "night-run/task-a",
                "review_round": 1, "completed_summary": "", "remaining_summary": "無理だった",
            },
        })
        night_runner.update_state_done(self.task, self.state, stdout)
        self.assertEqual(self.task["status"], "failed")

    def test_unverifiable_pr_marks_failed_even_if_self_reported_success(self):
        stdout = json.dumps({
            "is_error": False,
            "structured_output": {
                "status": "success", "pr_url": "https://github.com/x/y/pull/1",
                "branch": "night-run/task-a", "review_round": 1,
                "completed_summary": "done", "remaining_summary": "なし",
            },
        })
        with mock.patch.object(night_runner, "verify_pr", return_value=False):
            night_runner.update_state_done(self.task, self.state, stdout)
        self.assertEqual(self.task["status"], "failed")

    def test_verified_success_marks_done(self):
        stdout = json.dumps({
            "is_error": False,
            "structured_output": {
                "status": "success", "pr_url": "https://github.com/x/y/pull/1",
                "branch": "night-run/task-a", "review_round": 2,
                "completed_summary": "done", "remaining_summary": "なし",
            },
        })
        with mock.patch.object(night_runner, "verify_pr", return_value=True):
            night_runner.update_state_done(self.task, self.state, stdout)
        self.assertEqual(self.task["status"], "done")
        self.assertEqual(self.task["pr_url"], "https://github.com/x/y/pull/1")


class RateLimitEnvelopeTest(unittest.TestCase):
    def test_is_error_with_rate_limit_text_is_detected(self):
        envelope = {"is_error": True, "subtype": "error_during_execution", "result": "429 too many requests"}
        self.assertTrue(night_runner._envelope_is_rate_limited(envelope))

    def test_is_error_without_rate_limit_text_is_not_detected(self):
        envelope = {"is_error": True, "subtype": "error_max_turns", "result": "gave up after too many turns"}
        self.assertFalse(night_runner._envelope_is_rate_limited(envelope))

    def test_non_error_envelope_is_not_detected(self):
        envelope = {"is_error": False, "result": "usage limit"}  # is_errorでなければ対象外
        self.assertFalse(night_runner._envelope_is_rate_limited(envelope))

    def test_non_dict_is_not_detected(self):
        self.assertFalse(night_runner._envelope_is_rate_limited(None))


class RunTaskWithRetryRateLimitTest(unittest.TestCase):
    """returncode 0 + JSON封筒内でのレートリミット報告が、update_state_doneで
    即failedにされず、backoffリトライへ回ることを確認する(コードレビュー指摘の
    再現ケース)。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_path = os.path.join(self.tmp.name, "night-run-state.json")
        for name, value in [
            ("STATE_FILE", self.state_path),
            ("ALERTS_LOG", os.path.join(self.tmp.name, "alerts.log")),
            ("MAX_RETRY_ATTEMPTS", 2),
        ]:
            patcher = mock.patch.object(night_runner, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.task = {"title": "タスクA", "status": "pending", "branch": "night-run/task-a"}
        state = {
            "hard_limit": "2999-01-01T00:00:00+09:00",
            "tasks": [self.task],
        }
        with open(self.state_path, "w") as f:
            json.dump(state, f)
        self.state = state

    def test_rate_limited_envelope_retries_then_succeeds(self):
        rate_limited_stdout = json.dumps({
            "is_error": True, "subtype": "error_during_execution", "result": "429 rate limit",
        })
        success_stdout = json.dumps({
            "is_error": False,
            "structured_output": {
                "status": "success", "pr_url": "https://github.com/x/y/pull/1",
                "branch": "night-run/task-a", "review_round": 1,
                "completed_summary": "done", "remaining_summary": "なし",
            },
        })
        responses = [(0, rate_limited_stdout, ""), (0, success_stdout, "")]

        with mock.patch.object(night_runner, "run_claude_with_timeout", side_effect=responses), \
             mock.patch.object(night_runner, "build_prompt", return_value="prompt"), \
             mock.patch.object(night_runner, "time") as mock_time, \
             mock.patch.object(night_runner, "verify_pr", return_value=True):
            night_runner.run_task_with_retry(self.task, self.state)

        mock_time.sleep.assert_called_once()  # backoffで一度待ってからリトライしたこと
        final_state = night_runner.load_state()
        final_task = final_state["tasks"][0]
        self.assertEqual(final_task["status"], "done")  # 一度目でfailed確定していないこと

    def test_rate_limited_envelope_gives_up_after_max_attempts(self):
        rate_limited_stdout = json.dumps({
            "is_error": True, "subtype": "error_during_execution", "result": "429 rate limit",
        })
        # MAX_RETRY_ATTEMPTS=2に対して3回とも同じレートリミット応答
        responses = [(0, rate_limited_stdout, "")] * 3

        with mock.patch.object(night_runner, "run_claude_with_timeout", side_effect=responses), \
             mock.patch.object(night_runner, "build_prompt", return_value="prompt"), \
             mock.patch.object(night_runner, "time"), \
             mock.patch.object(night_runner, "save_diagnostic_branch", return_value="diagnostic/x"):
            night_runner.run_task_with_retry(self.task, self.state)

        final_state = night_runner.load_state()
        final_task = final_state["tasks"][0]
        self.assertEqual(final_task["status"], "failed")


class GitCleanupRetryTest(unittest.TestCase):
    def test_succeeds_on_second_attempt_without_raising(self):
        with mock.patch.object(
            night_runner, "git_cleanup",
            side_effect=[subprocess.CalledProcessError(1, ["git", "fetch"]), None],
        ), mock.patch.object(night_runner, "notify_human") as mock_notify, \
             mock.patch.object(night_runner, "time") as mock_time:
            night_runner.git_cleanup_with_retry(max_attempts=3, wait_seconds=1)

        mock_time.sleep.assert_called_once_with(1)
        mock_notify.assert_called_once()

    def test_raises_after_exhausting_all_attempts(self):
        error = subprocess.CalledProcessError(1, ["git", "fetch"])
        with mock.patch.object(night_runner, "git_cleanup", side_effect=[error, error, error]), \
             mock.patch.object(night_runner, "notify_human"), \
             mock.patch.object(night_runner, "time"):
            with self.assertRaises(subprocess.CalledProcessError):
                night_runner.git_cleanup_with_retry(max_attempts=3, wait_seconds=1)


class DraftPrBodyTest(unittest.TestCase):
    def test_body_has_no_todo_placeholder_and_embeds_progress(self):
        task = {
            "title": "タスクB",
            "step": "レビュー",
            "review_round": 2,
            "completed_summary": "画面Aを実装した",
        }
        with mock.patch.object(night_runner, "subprocess") as mock_subprocess:
            night_runner.create_draft_pr_from_branch(task, "diagnostic/task-b-1", "hard_limit_exceeded")

        create_call = next(
            c for c in mock_subprocess.run.call_args_list if c.args[0][0:2] == ["gh", "pr"]
        )
        argv = create_call.args[0]
        body_index = argv.index("--body") + 1
        body = argv[body_index]

        self.assertNotIn("TODO", body)
        self.assertIn("レビュー", body)
        self.assertIn("画面Aを実装した", body)


if __name__ == "__main__":
    unittest.main()
