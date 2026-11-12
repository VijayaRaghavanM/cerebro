import json
from pathlib import Path

import pytest
from eval_helpers import answer, golden_line
from typer.testing import CliRunner

from cerebro import bootstrap
from cerebro.adapters.jsonl_evaluation import JsonlRunStore
from cerebro.application import judging
from cerebro.application.evaluation import (
    Mismatch,
    Progress,
    ReplayReport,
    RunReport,
)
from cerebro.domain.evaluation import Failure, RunResult, Split, Verdict
from cerebro.interfaces.cli import app
from cerebro.ports.agent import RateLimited


class Calls:
    """What the CLI handed to bootstrap.run_eval."""

    def __init__(self) -> None:
        self.args: dict[str, object] = {}


# The real bootstrap.run_eval asks a model, so these tests replace it at this seam.
def fake_run_eval(monkeypatch: pytest.MonkeyPatch, report: RunReport) -> Calls:
    calls = Calls()

    def run_eval(
        model: bootstrap.Contestant,
        split: Split | None = None,
        *,
        limit: int | None = None,
        run_name: str | None = None,
        progress: Progress | None = None,
    ) -> RunReport:
        calls.args = {"model": model, "split": split, "limit": limit, "run": run_name}
        assert progress is not None
        progress(RunResult("a", "m", (), answer()))
        progress(RunResult("b", "m", (), Failure("RateLimited", "")))
        return report

    monkeypatch.setattr(bootstrap, "run_eval", run_eval)
    return calls


def test_eval_run_passes_its_options_through(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_run_eval(monkeypatch, RunReport(answered=1, failed=1, skipped=3))

    result = CliRunner().invoke(
        app,
        [
            "eval", "run",
            "--model", "ministral-3b-openrouter",
            "--split", "test",
            "--limit", "5",
            "--run", "trial",
        ],
    )  # fmt: skip

    assert result.exit_code == 0
    assert calls.args == {
        "model": bootstrap.Contestant.MINISTRAL_3B_OPENROUTER,
        "split": Split.TEST,
        "limit": 5,
        "run": "trial",
    }


def test_eval_run_defaults_to_both_splits_and_all_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = fake_run_eval(monkeypatch, RunReport(answered=0, failed=0, skipped=0))

    CliRunner().invoke(app, ["eval", "run", "--model", "ministral-14b"])

    assert calls.args == {
        "model": bootstrap.Contestant.MINISTRAL_14B,
        "split": None,
        "limit": None,
        "run": None,
    }


def test_eval_run_prints_each_question_and_a_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_run_eval(monkeypatch, RunReport(answered=1, failed=1, skipped=3))

    result = CliRunner().invoke(app, ["eval", "run", "--model", "ministral-14b"])

    assert result.output == (
        "a: answered\n"
        "b: failed (RateLimited)\n"
        "1 answered, 1 failed, 3 already answered\n"
    )


def fake_replay_run(monkeypatch: pytest.MonkeyPatch, report: ReplayReport) -> list[str]:
    """Replaces the replay, and returns the run names it was asked to replay."""
    asked: list[str] = []

    def replay_run(run_name: str) -> ReplayReport:
        asked.append(run_name)
        return report

    monkeypatch.setattr(bootstrap, "replay_run", replay_run)
    return asked


def test_eval_replay_says_how_many_answers_were_reproduced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = fake_replay_run(monkeypatch, ReplayReport(checked=4, mismatches=()))

    result = CliRunner().invoke(app, ["eval", "replay", "trial"])

    assert result.exit_code == 0
    assert result.output == "4 of 4 answers reproduced exactly\n"
    assert asked == ["trial"]


def test_eval_replay_lists_each_mismatch_and_exits_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = ReplayReport(
        checked=4, mismatches=(Mismatch("g002", "step 2: saved x, replayed y"),)
    )
    fake_replay_run(monkeypatch, report)

    result = CliRunner().invoke(app, ["eval", "replay", "trial"])

    assert result.exit_code == 1
    assert result.output == (
        "g002: step 2: saved x, replayed y\n3 of 4 answers reproduced exactly\n"
    )


def test_eval_replay_of_a_run_with_no_answers_says_so(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_replay_run(monkeypatch, ReplayReport(checked=0, mismatches=()))

    result = CliRunner().invoke(app, ["eval", "replay", "trial"])

    assert result.exit_code == 1
    assert result.output == "No answered questions in runs/trial.\n"


def test_eval_replay_of_a_run_without_exchanges_says_which_question(
    data_dir: Path,
) -> None:
    (data_dir / "evals").mkdir()
    (data_dir / "evals" / "golden.jsonl").write_text(
        json.dumps(golden_line("a")) + "\n"
    )
    JsonlRunStore(data_dir / "runs" / "trial").append(
        RunResult("a", "ministral-14b", (), answer())
    )

    result = CliRunner().invoke(app, ["eval", "replay", "trial"])

    assert result.exit_code == 1
    assert result.output == "a: its model exchanges were not saved.\n"


def test_eval_score_writes_the_scores_and_report_and_prints_the_totals(
    data_dir: Path,
) -> None:
    (data_dir / "evals").mkdir()
    (data_dir / "evals" / "golden.jsonl").write_text(
        json.dumps(golden_line("a")) + "\n"
    )
    JsonlRunStore(data_dir / "runs" / "trial").append(
        RunResult("a", "ministral-14b", (), answer())
    )

    result = CliRunner().invoke(app, ["eval", "score", "trial"])

    assert result.exit_code == 0
    assert result.output == "1 of 1 solved, fact recall 100%, cost $0.0000\n"
    assert (data_dir / "runs" / "trial" / "scores.json").exists()
    assert (data_dir / "runs" / "trial" / "report.md").exists()


def test_eval_judge_prints_each_verdict_and_a_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[str] = []

    def judge_run(
        run_name: str, progress: judging.Progress | None = None
    ) -> judging.JudgeReport:
        asked.append(run_name)
        assert progress is not None
        progress("a", Verdict(True, "Right."))
        progress("b", Verdict(False, "Wrong."))
        return judging.JudgeReport(judged=2, correct=1, skipped=3)

    monkeypatch.setattr(bootstrap, "judge_run", judge_run)

    result = CliRunner().invoke(app, ["eval", "judge", "trial"])

    assert result.exit_code == 0
    assert asked == ["trial"]
    assert result.output == (
        "a: correct\nb: incorrect\n2 judged, 1 correct, 3 already judged\n"
    )


def test_eval_judge_without_a_key_says_which_variable_to_set(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)

    result = CliRunner().invoke(app, ["eval", "judge", "trial"])

    assert result.exit_code == 1
    assert result.output == "Set CEREBRAS_API_KEY to judge a run.\n"


def test_eval_judge_that_is_rate_limited_says_the_verdicts_are_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def judge_run(
        run_name: str, progress: judging.Progress | None = None
    ) -> judging.JudgeReport:
        raise RateLimited("slow down")

    monkeypatch.setattr(bootstrap, "judge_run", judge_run)

    result = CliRunner().invoke(app, ["eval", "judge", "trial"])

    assert result.exit_code == 1
    assert "Verdicts are kept" in result.output


def test_eval_score_uses_the_verdicts_a_judge_kept(data_dir: Path) -> None:
    (data_dir / "evals").mkdir()
    (data_dir / "evals" / "golden.jsonl").write_text(
        json.dumps(golden_line("a")) + "\n"
    )
    store = JsonlRunStore(data_dir / "runs" / "trial")
    store.append(RunResult("a", "ministral-14b", (), answer()))
    store.save_verdict("a", Verdict(False, "Wrong."))

    result = CliRunner().invoke(app, ["eval", "score", "trial"])

    assert result.output == "0 of 1 solved, fact recall 100%, cost $0.0000\n"


def test_eval_score_of_a_run_with_no_results_says_so(data_dir: Path) -> None:
    (data_dir / "evals").mkdir()
    (data_dir / "evals" / "golden.jsonl").write_text(
        json.dumps(golden_line("a")) + "\n"
    )

    result = CliRunner().invoke(app, ["eval", "score", "trial"])

    assert result.exit_code == 1
    assert result.output == "No results in runs/trial.\n"


def test_eval_run_without_golden_questions_says_where_they_belong(
    data_dir: Path,
) -> None:
    result = CliRunner().invoke(app, ["eval", "run", "--model", "ministral-14b"])

    assert result.exit_code == 1
    assert result.output == ("No golden questions: evals/golden.jsonl is missing.\n")


def test_eval_run_without_a_key_says_which_variable_to_set(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    (data_dir / "evals").mkdir()
    (data_dir / "evals" / "golden.jsonl").write_text(
        json.dumps(golden_line("a")) + "\n"
    )

    result = CliRunner().invoke(app, ["eval", "run", "--model", "ministral-14b"])

    assert result.exit_code == 1
    assert result.output == "Set MISTRAL_API_KEY to run the evaluation.\n"
