"""The golden questions and a run's results as JSONL files."""

import json
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

from cerebro.domain.answers import Answer, Source, ToolCall, ToolReply
from cerebro.domain.evaluation import (
    Failure,
    GoldenQuestion,
    Outcome,
    RunResult,
    Split,
)
from cerebro.ports.evaluation import GoldenSet, RunStore


class JsonlGoldenSet(GoldenSet):
    """The golden questions in one file, a JSON object per line."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def questions(self, split: Split | None) -> list[GoldenQuestion]:
        with self.path.open(encoding="utf-8") as fh:
            questions = [_question(json.loads(line)) for line in fh if line.strip()]

        return [q for q in questions if split is None or q.split == split]


class JsonlRunStore(RunStore):
    """A run's results in `results.jsonl` in its folder, one line per question.

    Results are only ever appended, so a stopped run resumes where it stopped. A
    question tried again has two lines; reading keeps the later one.
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

        # Append mode: results already in the file are never rewritten.
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(_result_to_json(result)) + "\n")

    def results(self) -> Iterator[RunResult]:
        if not self.path.exists():
            return

        # A repeated id keeps its first place in the dict and takes the later value.
        latest: dict[str, RunResult] = {}
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                result = _result_from_json(json.loads(line))
                latest[result.question_id] = result

        yield from latest.values()


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
