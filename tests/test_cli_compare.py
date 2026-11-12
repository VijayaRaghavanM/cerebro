import json
from dataclasses import replace
from pathlib import Path

from eval_helpers import answer, golden_line
from typer.testing import CliRunner

from cerebro.adapters.jsonl_evaluation import JsonlRunStore
from cerebro.domain.evaluation import RunResult, Verdict
from cerebro.interfaces.cli import app

HEADER = (
    "| Run | Model | Questions | Solved | Judge correct | Fact recall "
    "| Citation recall | Citation precision | Refusals right | Mean seconds "
    "| Mean tokens | Cost | Cost per solved |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
)

# Two runs on three questions. The first model charges $0.20 per million tokens,
# the second is free. Every answer is 100,040 tokens, so each costs two cents.
EXPECTED = (
    HEADER + "| alpha | ministral-14b-openrouter | 3 | 2 (67%) | - | 67% | 67% | 100% "
    "| 100% | 12.5 | 100040 | $0.0600 | $0.0300 |\n"
    "| beta | qwen3-14b-ollama | 2 | 1 (50%) | 50% | 100% | 100% | 100% "
    "| 100% | 12.5 | 100040 | $0.0000 | $0.0000 |\n"
    "\n"
    "| Category | alpha | beta |\n"
    "| --- | --- | --- |\n"
    "| identity | 1 of 2 | 1 of 1 |\n"
    "| comics | 1 of 1 | 0 of 1 |\n"
    "\n"
    "beta: judge agrees with labels on 50%, kappa 0.00, 2 compared\n"
)


def write_runs(data_dir: Path) -> None:
    (data_dir / "evals").mkdir()
    lines = [
        golden_line("a"),
        golden_line("b"),
        golden_line("c", category="comics"),
    ]
    (data_dir / "evals" / "golden.jsonl").write_text(
        "".join(json.dumps(line) + "\n" for line in lines)
    )
    big = replace(answer(), input_tokens=100_000)
    wrong = replace(big, text="Nobody.", sources=())

    alpha = JsonlRunStore(data_dir / "runs" / "alpha")
    alpha.append(RunResult("a", "ministral-14b-openrouter", (), big))
    alpha.append(RunResult("b", "ministral-14b-openrouter", (), wrong))
    alpha.append(RunResult("c", "ministral-14b-openrouter", (), big))

    beta = JsonlRunStore(data_dir / "runs" / "beta")
    beta.append(RunResult("a", "qwen3-14b-ollama", (), big))
    beta.append(RunResult("c", "qwen3-14b-ollama", (), big))
    beta.save_verdict("a", Verdict(True, "."))
    beta.save_verdict("c", Verdict(False, "."))
    labels = [{"question_id": q, "correct": True, "reason": "By hand."} for q in "ac"]
    (data_dir / "runs" / "beta" / "labels.jsonl").write_text(
        "".join(json.dumps(label) + "\n" for label in labels)
    )


def test_eval_compare_prints_both_tables_and_the_agreement(data_dir: Path) -> None:
    write_runs(data_dir)

    result = CliRunner().invoke(app, ["eval", "compare", "alpha", "beta"])

    assert result.exit_code == 0
    assert result.output == EXPECTED


def test_eval_compare_out_writes_the_file_instead_of_printing(data_dir: Path) -> None:
    write_runs(data_dir)
    target = data_dir / "compare.md"

    result = CliRunner().invoke(
        app, ["eval", "compare", "alpha", "beta", "--out", str(target)]
    )

    assert result.exit_code == 0
    assert result.output == ""
    assert target.read_text() == EXPECTED


def test_eval_compare_keeps_no_scores_in_the_runs(data_dir: Path) -> None:
    write_runs(data_dir)

    CliRunner().invoke(app, ["eval", "compare", "alpha", "beta"])

    assert not (data_dir / "runs" / "alpha" / "scores.json").exists()
    assert not (data_dir / "runs" / "beta" / "report.md").exists()


def test_eval_compare_of_a_run_with_no_results_says_which(data_dir: Path) -> None:
    write_runs(data_dir)

    result = CliRunner().invoke(app, ["eval", "compare", "alpha", "missing"])

    assert result.exit_code == 1
    assert result.output == "No results in runs/missing.\n"
