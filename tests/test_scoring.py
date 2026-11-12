import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from eval_helpers import answer, golden_question

from cerebro.adapters.jsonl_evaluation import JsonlRunStore
from cerebro.application.report import COLUMNS, render_report
from cerebro.application.scoring import (
    facts_found,
    observed_outcome,
    score,
    score_run,
    summarise,
)
from cerebro.domain.answers import Answer, Source, ToolCall
from cerebro.domain.evaluation import Failure, Outcome, RunResult
from cerebro.domain.scoring import Price, Score

FREE = Price(0, 0)
HOWLETT = Source("James Howlett (Earth-616)", "https://example.test/a")


def cites(*sources: Source, text: str = "James Howlett [1].") -> Answer:
    return replace(answer(text), sources=sources)


def scored(final: Answer | Failure, **changes: Any) -> Score:
    question = replace(golden_question("a"), **changes)
    return score(question, RunResult("a", "m", (), final), FREE)


# Observed outcome


def test_an_answer_that_cannot_find_it_and_cites_nothing_is_a_refusal() -> None:
    question = golden_question("a")
    final = cites(text="I couldn’t find that in the records.")

    assert observed_outcome(question, final) == Outcome.REFUSE


def test_a_refusal_that_cites_a_source_is_an_answer() -> None:
    question = golden_question("a")
    final = cites(HOWLETT, text="I couldn't find that in the records.")

    assert observed_outcome(question, final) == Outcome.ANSWER


def test_an_answer_ending_in_a_question_is_a_clarification() -> None:
    question = golden_question("a")
    final = cites(text="Which Captain Marvel do you mean?")

    assert observed_outcome(question, final) == Outcome.CLARIFY


def test_an_answer_naming_two_expected_pages_is_a_clarification() -> None:
    question = replace(
        golden_question("a"),
        expected_pages=("Mar-Vell (Earth-616)", "Carol Danvers (Earth-616)"),
    )
    final = cites(text="Mar-Vell and Carol Danvers have both used the name.")

    assert observed_outcome(question, final) == Outcome.CLARIFY


def test_an_answer_naming_one_expected_page_is_an_answer() -> None:
    question = replace(
        golden_question("a"),
        expected_pages=("Mar-Vell (Earth-616)", "Carol Danvers (Earth-616)"),
    )

    assert observed_outcome(question, cites(text="It is Mar-Vell.")) == Outcome.ANSWER


def test_a_failure_is_its_own_outcome() -> None:
    final = Failure("RateLimited", "slow down")

    assert observed_outcome(golden_question("a"), final) == Outcome.FAILED


# Facts


def test_a_fact_is_found_whatever_the_case_punctuation_or_separators() -> None:
    text = "Spider-Man sold 18154 copies, said JAMES HOWLETT."

    assert facts_found(("spider man", "18,154", "James Howlett"), text) == 3


def test_a_fact_in_the_answer_with_separators_matches_one_without() -> None:
    assert facts_found(("18154",), "It sold 18,154 copies.") == 1


def test_a_number_is_not_found_inside_a_longer_one() -> None:
    assert facts_found(("58",), "There were 158 of them.") == 0


# Citations


def test_citation_recall_and_precision_count_expected_pages() -> None:
    final = cites(HOWLETT, Source("Logan (Earth-616)", "https://example.test/b"))

    result = scored(final, expected_pages=("James Howlett (Earth-616)", "Other"))

    assert (result.pages_cited, result.pages_expected, result.cited_total) == (1, 2, 2)


def test_a_comic_vine_source_is_neither_relevant_nor_irrelevant() -> None:
    final = cites(HOWLETT, Source("Comic Vine: Wolverine", "https://example.test/c"))

    result = scored(final)

    assert (result.pages_cited, result.cited_total) == (1, 1)


# Tools


def test_tools_are_scored_from_the_trace() -> None:
    question = golden_question("a")
    trace = (
        ToolCall("read_page", "James Howlett (Earth-616)"),
        ToolCall("search_pages", "Wolverine"),
        ToolCall("other_tool", "x"),
    )

    result = score(question, RunResult("a", "m", trace, answer()), FREE)

    assert (result.tools_used, result.tools_expected) == (2, 2)
    assert not result.in_order


def test_tools_called_in_the_expected_order_are_in_order() -> None:
    question = golden_question("a")
    trace = (
        ToolCall("search_pages", "Wolverine"),
        ToolCall("read_page", "James Howlett (Earth-616)"),
        ToolCall("search_pages", "Logan"),
    )

    result = score(question, RunResult("a", "m", trace, answer()), FREE)

    assert result.in_order


# Cost


def test_cost_is_dollars_per_million_input_and_output_tokens() -> None:
    question = golden_question("a")  # the answer used 1200 in and 40 out

    result = score(question, RunResult("a", "m", (), answer()), Price(1.0, 10.0))

    assert result.cost == (1200 * 1.0 + 40 * 10.0) / 1_000_000


# Solved


def test_an_answer_with_every_fact_and_an_expected_page_is_solved() -> None:
    assert scored(cites(HOWLETT)).solved


def test_an_answer_that_cites_no_expected_page_is_not_solved() -> None:
    other = Source("Someone Else (Earth-616)", "https://example.test/d")

    assert not scored(cites(other)).solved


def test_an_answer_missing_a_fact_is_not_solved() -> None:
    assert not scored(cites(HOWLETT, text="Somebody [1]."), expected_pages=()).solved


def test_a_question_with_no_expected_pages_needs_no_citation() -> None:
    assert scored(cites(text="James Howlett."), expected_pages=()).solved


def test_a_refusal_is_solved_when_refusal_was_expected() -> None:
    final = cites(text="I couldn't find that in the records.")

    result = scored(
        final,
        expected_outcome=Outcome.REFUSE,
        expected_facts=(),
        expected_pages=(),
    )

    assert result.solved


def test_a_failure_is_not_solved() -> None:
    assert not scored(Failure("ProviderError", "down"), expected_facts=()).solved


# Summaries and report


def test_a_summary_adds_up_each_category_and_all_of_them() -> None:
    first = replace(golden_question("a"), category="lookup")
    second = replace(golden_question("b"), category="lookup")
    third = replace(golden_question("c"), category="multi-hop")
    price = Price(1.0, 1.0)
    results = [
        (first, RunResult("a", "m", (), cites(HOWLETT))),
        (second, RunResult("b", "m", (), cites(text="Nobody."))),
        (third, RunResult("c", "m", (), Failure("RateLimited", ""))),
    ]
    scores = [score(question, result, price) for question, result in results]

    lookup, multi_hop, overall = summarise(scores)

    assert (lookup.name, lookup.questions, lookup.solved) == ("lookup", 2, 1)
    assert (multi_hop.name, multi_hop.solved) == ("multi-hop", 0)
    assert (overall.name, overall.questions, overall.solved) == ("overall", 3, 1)
    assert overall.facts_expected == 3
    assert overall.facts_found == 1
    assert overall.tokens == 2 * 1240
    assert overall.cost == pytest.approx(2 * 1240 / 1_000_000)
    assert lookup.cost == overall.cost


def test_the_report_has_a_header_row_and_a_row_per_summary() -> None:
    result = RunResult("a", "m", (), cites(HOWLETT))
    scores = [score(golden_question("a"), result, FREE)]

    lines = render_report(summarise(scores)).splitlines()

    assert lines[0] == "| " + " | ".join(COLUMNS) + " |"
    assert lines[2].startswith("| identity | 1 | 1 | 100% |")
    assert lines[3].startswith("| overall | 1 | 1 | 100% |")
    assert len(lines) == 4


# The use case


def test_a_run_is_scored_and_its_scores_and_report_are_kept(tmp_path: Path) -> None:
    store = JsonlRunStore(tmp_path)
    store.append(RunResult("a", "m", (), cites(HOWLETT)))
    store.append(RunResult("zzz", "m", (), cites(HOWLETT)))  # not in the golden set

    line = score_run([golden_question("a")], store, {"m": FREE})

    assert line == "1 of 1 solved, fact recall 100%, cost $0.0000"
    kept = json.loads((tmp_path / "scores.json").read_text())
    assert [score["question_id"] for score in kept] == ["a"]
    assert kept[0]["solved"] is True
    assert (tmp_path / "report.md").read_text().startswith("| Category |")


def test_a_run_with_no_results_is_not_scored(tmp_path: Path) -> None:
    store = JsonlRunStore(tmp_path)

    assert score_run([golden_question("a")], store, {}) is None
    assert not (tmp_path / "report.md").exists()
