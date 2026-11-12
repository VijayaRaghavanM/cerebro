import json
from pathlib import Path

import pytest
from eval_helpers import answer, golden_line
from typer.testing import CliRunner

from cerebro import bootstrap
from cerebro.application.evaluation import Progress, RunReport
from cerebro.domain.evaluation import Failure, RunResult, Split
from cerebro.interfaces.cli import app


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
