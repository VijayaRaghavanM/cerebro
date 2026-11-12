"""The golden questions and a run's results as JSONL files."""

import json
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

from cerebro.domain.answers import Answer, Source, ToolCall, ToolReply
from cerebro.domain.evaluation import (
    Exchange,
    Failure,
    GoldenQuestion,
    Outcome,
    RunResult,
    Split,
    Verdict,
)
from cerebro.domain.scoring import Score
from cerebro.ports.evaluation import ExchangesMissing, GoldenSet, RunStore


class JsonlGoldenSet(GoldenSet):
    """The golden questions in one file, a JSON object per line."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def questions(self, split: Split | None) -> list[GoldenQuestion]:
        with self.path.open(encoding="utf-8") as fh:
            questions = [_question(json.loads(line)) for line in fh if line.strip()]

        return [q for q in questions if split is None or q.split == split]


class JsonlRunStore(RunStore):
    """A run's results in `results.jsonl` in its folder, one line per question,
    and each question's model exchanges in `exchanges/<question id>.json`. The
    judge's verdicts are in `verdicts.jsonl`, the hand labels a person wrote to
    check them against are in `labels.jsonl`, and the scores are `scores.json` and
    `report.md`.

    Results are only ever appended, so a stopped run resumes where it stopped. A
    question tried again has two lines; reading keeps the later one, and its
    exchanges file is written over.
    """

    def __init__(self, folder: Path) -> None:
        self.path = folder / "results.jsonl"

    def answered_ids(self) -> set[str]:
        return {
            result.question_id
            for result in self.results()
            if isinstance(result.final, Answer)
        }

    def append(self, result: RunResult) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        _append_line(self.path, _result_to_json(result))

    def results(self) -> Iterator[RunResult]:
        if not self.path.exists():
            return

        # A repeated id keeps its first place in the dict and takes the later value.
        latest: dict[str, RunResult] = {}
        for data in _read_records(self.path):
            result = _result_from_json(data)
            latest[result.question_id] = result

        yield from latest.values()

    def save_exchanges(self, question_id: str, exchanges: list[Exchange]) -> None:
        path = self._exchanges_path(question_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(json.dumps(exchanges, indent=2) + "\n", encoding="utf-8")

    def exchanges(self, question_id: str) -> list[Exchange]:
        path = self._exchanges_path(question_id)
        if not path.exists():
            raise ExchangesMissing(question_id)

        exchanges: list[Exchange] = json.loads(path.read_text(encoding="utf-8"))
        return exchanges

    def save_verdict(self, question_id: str, verdict: Verdict) -> None:
        # Append mode, as with results: a stopped judging run resumes where it stopped.
        line = {"question_id": question_id, **asdict(verdict)}
        _append_line(self._verdicts_path(), line)

    def verdicts(self) -> dict[str, Verdict]:
        return _read_rulings(self._verdicts_path())

    def labels(self) -> dict[str, Verdict]:
        return _read_rulings(self.path.parent / "labels.jsonl")

    def save_scores(self, scores: list[Score], report: str) -> None:
        folder = self.path.parent
        folder.mkdir(parents=True, exist_ok=True)

        as_json = json.dumps([asdict(score) for score in scores], indent=2)
        (folder / "scores.json").write_text(as_json + "\n", encoding="utf-8")
        (folder / "report.md").write_text(report, encoding="utf-8")

    def _exchanges_path(self, question_id: str) -> Path:
        return self.path.parent / "exchanges" / f"{question_id}.json"

    def _verdicts_path(self) -> Path:
        return self.path.parent / "verdicts.jsonl"


def _read_rulings(path: Path) -> dict[str, Verdict]:
    if not path.exists():
        return {}

    # A repeated id takes the later ruling.
    kept: dict[str, Verdict] = {}
    for data in _read_records(path):
        kept[data["question_id"]] = Verdict(data["correct"], data["reason"])

    return kept


def _read_records(path: Path) -> list[dict[str, Any]]:
    """Every record in a JSONL file.

    A crash in the middle of a write leaves a last line with no newline and only
    part of a record. That record never finished, so it is left out and its
    question is done again. Any other bad line is real damage and raises.
    """
    finished, _, tail = path.read_text(encoding="utf-8").rpartition("\n")
    lines = finished.split("\n") if finished else []
    records = [json.loads(line) for line in lines]

    if tail:
        try:
            records.append(json.loads(tail))
        except json.JSONDecodeError:
            pass

    return records


def _append_line(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        _drop_torn_tail(path)

    # Append mode: records already in the file are never rewritten.
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(data) + "\n")


def _drop_torn_tail(path: Path) -> None:
    """Cut an unfinished last line off before an append, so the new record is not
    glued to it and no bad line is left in the middle of the file.
    """
    raw = path.read_bytes()
    tail = raw.rpartition(b"\n")[2]
    if not tail:
        return

    try:
        json.loads(tail)
    except json.JSONDecodeError:
        with path.open("r+b") as fh:
            fh.truncate(len(raw) - len(tail))
    else:
        # A whole record that only lost its newline is kept.
        with path.open("ab") as fh:
            fh.write(b"\n")


def _question(data: dict[str, Any]) -> GoldenQuestion:
    return GoldenQuestion(
        id=data["id"],
        split=Split(data["split"]),
        category=data["category"],
        question=data["question"],
        expected_outcome=Outcome(data["expected_outcome"]),
        expected_facts=tuple(data["expected_facts"]),
        expected_pages=tuple(data["expected_pages"]),
        expected_tools=tuple(data["expected_tools"]),
        source=data["source"],
        source_url=data["source_url"],
        license=data["license"],
        original=data.get("original"),
        source_author=data.get("source_author"),
    )


def _result_to_json(result: RunResult) -> dict[str, Any]:
    answer = result.final if isinstance(result.final, Answer) else None
    failure = result.final if isinstance(result.final, Failure) else None

    return {
        "question_id": result.question_id,
        "model": result.model,
        "trace": [_step_to_json(step) for step in result.trace],
        "answer": asdict(answer) if answer else None,
        "failure": asdict(failure) if failure else None,
    }


def _step_to_json(step: ToolCall | ToolReply) -> dict[str, str]:
    match step:
        case ToolCall():
            return {"kind": "call", "tool": step.tool, "argument": step.argument}
        case ToolReply():
            return {"kind": "reply", "tool": step.tool, "text": step.text}


def _result_from_json(data: dict[str, Any]) -> RunResult:
    final: Answer | Failure
    if data["answer"] is not None:
        sources = tuple(Source(**source) for source in data["answer"]["sources"])
        final = Answer(**{**data["answer"], "sources": sources})
    else:
        final = Failure(**data["failure"])

    return RunResult(
        question_id=data["question_id"],
        model=data["model"],
        trace=tuple(_step_from_json(step) for step in data["trace"]),
        final=final,
    )


def _step_from_json(data: dict[str, str]) -> ToolCall | ToolReply:
    if data["kind"] == "call":
        return ToolCall(data["tool"], data["argument"])

    return ToolReply(data["tool"], data["text"])
