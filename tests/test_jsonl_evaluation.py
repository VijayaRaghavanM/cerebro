import json
from pathlib import Path

from eval_helpers import answer, golden_line, golden_question

from cerebro.adapters.jsonl_evaluation import JsonlGoldenSet, JsonlRunStore
from cerebro.domain.answers import ToolCall, ToolReply
from cerebro.domain.evaluation import Failure, Outcome, RunResult, Split


def write_golden(path: Path, *lines: dict[str, object]) -> None:
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))


def test_golden_questions_are_read_with_their_optional_fields(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    write_golden(
        path,
        golden_line("a"),
        golden_line(
            "b",
            "test",
            original="Who is Logan?",
            source_author="A. Writer",
            expected_outcome="refuse",
            expected_facts=[],
        ),
    )

    first, second = JsonlGoldenSet(path).questions(None)

    assert first == golden_question("a")
    assert first.original is None
    assert first.source_author is None
    assert second.split == Split.TEST
    assert second.expected_outcome == Outcome.REFUSE
    assert second.expected_facts == ()
    assert second.original == "Who is Logan?"
    assert second.source_author == "A. Writer"


def test_golden_questions_can_be_limited_to_one_split(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    write_golden(
        path, golden_line("a", "dev"), golden_line("b", "test"), golden_line("c")
    )

    golden = JsonlGoldenSet(path)

    assert [q.id for q in golden.questions(Split.DEV)] == ["a", "c"]
    assert [q.id for q in golden.questions(Split.TEST)] == ["b"]
    assert [q.id for q in golden.questions(None)] == ["a", "b", "c"]


def test_results_appended_in_one_run_are_read_back_in_the_next(tmp_path: Path) -> None:
    answered = RunResult(
        "a",
        "ministral-14b",
        (
            ToolCall("search_pages", "Wolverine"),
            ToolReply("search_pages", "James Howlett (Earth-616)"),
        ),
        answer(),
    )
    failed = RunResult(
        "b",
        "ministral-14b",
        (ToolCall("read_page", "Thor"),),
        Failure("RateLimited", ""),
    )

    JsonlRunStore(tmp_path / "run").append(answered)
    JsonlRunStore(tmp_path / "run").append(failed)

    store = JsonlRunStore(tmp_path / "run")
    assert list(store.results()) == [answered, failed]
    assert store.answered_ids() == {"a"}


def test_a_question_tried_again_has_its_latest_result_in_its_first_place(
    tmp_path: Path,
) -> None:
    failed = RunResult("a", "m", (), Failure("RateLimited", ""))
    other = RunResult("b", "m", (), answer())
    retried = RunResult("a", "m", (), answer("Second try."))

    store = JsonlRunStore(tmp_path)
    store.append(failed)
    store.append(other)
    assert store.answered_ids() == {"b"}

    store.append(retried)
    assert list(store.results()) == [retried, other]
    assert store.answered_ids() == {"a", "b"}


def test_the_latest_result_decides_whether_a_question_is_answered(
    tmp_path: Path,
) -> None:
    store = JsonlRunStore(tmp_path)
    store.append(RunResult("a", "m", (), answer()))
    store.append(RunResult("a", "m", (), Failure("RateLimited", "")))

    assert store.answered_ids() == set()


def test_a_run_with_no_results_yet_is_empty(tmp_path: Path) -> None:
    store = JsonlRunStore(tmp_path / "never-started")

    assert store.answered_ids() == set()
    assert list(store.results()) == []


def test_each_result_is_one_line_of_results_jsonl(tmp_path: Path) -> None:
    store = JsonlRunStore(tmp_path / "run")
    store.append(RunResult("a", "m", (), answer()))
    store.append(RunResult("b", "m", (), answer()))

    lines = (tmp_path / "run" / "results.jsonl").read_text().splitlines()
    assert len(lines) == 2
