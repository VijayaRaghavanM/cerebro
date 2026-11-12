"""Score a run against the golden questions with rules that need no model.

Whether an answer is correct, beyond holding the expected facts, is for a judge.
When the run holds the judge's verdict on an answer, that decides whether it is
correct; the rules still score everything else.
"""

import re
from collections.abc import Mapping

from cerebro.application.report import overall_line, render_report
from cerebro.domain.answers import REFUSAL, Answer, ToolCall, is_comic_vine
from cerebro.domain.evaluation import (
    Failure,
    GoldenQuestion,
    Outcome,
    RunResult,
    Verdict,
)
from cerebro.domain.scoring import Price, Score, Summary
from cerebro.ports.evaluation import RunStore

# Without the leading "I", so a refusal in any person counts; plus the spelled-out form.
REFUSALS = (
    REFUSAL.removeprefix("I "),
    REFUSAL.removeprefix("I ").replace("couldn't", "could not"),
)

NOTHING = Answer("", (), 0, 0, 0, 0, 0.0)


def score_run(
    questions: list[GoldenQuestion], store: RunStore, prices: Mapping[str, Price]
) -> str | None:
    """Score every saved result, keep the scores and a report, and return the
    overall totals in one line, or None when the run has no results.

    `prices` is keyed by the model name a result carries.
    """
    scores = score_results(questions, store, prices)
    if not scores:
        return None

    summaries = summarise(scores)
    store.save_scores(scores, render_report(summaries))

    return overall_line(summaries[-1])


def score_results(
    questions: list[GoldenQuestion], store: RunStore, prices: Mapping[str, Price]
) -> list[Score]:
    """The score of every saved result, with the judge's verdict where the run has
    one. A result whose question is no longer in the golden set is left out.
    """
    by_id = {question.id: question for question in questions}
    verdicts = store.verdicts()

    return [
        score(
            by_id[result.question_id],
            result,
            prices[result.model],
            verdicts.get(result.question_id),
        )
        for result in store.results()
        if result.question_id in by_id
    ]


def score(
    question: GoldenQuestion,
    result: RunResult,
    price: Price,
    verdict: Verdict | None = None,
) -> Score:
    """How one result measures against its question, with the judge's verdict on
    its answer if there is one.
    """
    observed = observed_outcome(question, result.final)
    called = [step.tool for step in result.trace if isinstance(step, ToolCall)]

    # A failure scores as an empty answer that cost nothing.
    answer = result.final if isinstance(result.final, Answer) else NOTHING
    cited = cited_pages(answer)
    expected_cited = [title for title in cited if title in question.expected_pages]
    found = facts_found(question.expected_facts, answer.text)
    solved = is_solved(question, observed, found, len(expected_cited), verdict)

    return Score(
        question_id=question.id,
        category=question.category,
        expected=question.expected_outcome,
        observed=observed,
        facts_found=found,
        facts_expected=len(question.expected_facts),
        pages_cited=len(expected_cited),
        pages_expected=len(question.expected_pages),
        cited_total=len(cited),
        tools_used=len(set(called) & set(question.expected_tools)),
        tools_expected=len(question.expected_tools),
        in_order=tools_in_order(question.expected_tools, called),
        seconds=answer.seconds,
        input_tokens=answer.input_tokens,
        output_tokens=answer.output_tokens,
        cost=cost(answer.input_tokens, answer.output_tokens, price),
        solved=solved,
        judge_correct=verdict.correct if verdict else None,
    )


def observed_outcome(question: GoldenQuestion, final: Answer | Failure) -> Outcome:
    """What the response was: a failure, a refusal, a clarification or an answer.

    A refusal says it could not find the answer and cites nothing; one that cites
    a source is an answer. A clarification ends with a question mark, for any
    question. On a question that expects a clarification, it also counts when the
    reply names two or more of the expected pages, as when it lists the characters
    an ambiguous name could mean. On a question that expects an answer the
    expected pages are what a correct answer should cite, so a reply that names
    them, as a comparison does, is still an answer.
    """
    if isinstance(final, Failure):
        return Outcome.FAILED

    text = _normal(final.text)
    if not final.sources and any(_normal(phrase) in text for phrase in REFUSALS):
        return Outcome.REFUSE

    if final.text.rstrip().endswith("?"):
        return Outcome.CLARIFY

    if question.expected_outcome != Outcome.CLARIFY:
        return Outcome.ANSWER

    names = [_without_reality(title) for title in question.expected_pages]
    named = [name for name in names if _normal(name) in text]
    if len(named) >= 2:
        return Outcome.CLARIFY

    return Outcome.ANSWER


def facts_found(facts: tuple[str, ...], text: str) -> int:
    """How many expected facts the text holds, as whole words and numbers, with
    case, punctuation and thousands separators ignored.
    """
    words = _normal(text)

    return sum(1 for fact in facts if _normal(fact) in words)


def cited_pages(answer: Answer) -> list[str]:
    """The titles an answer cites, once each, without the Comic Vine records."""
    titles = [source.title for source in answer.sources if not is_comic_vine(source)]

    return list(dict.fromkeys(titles))


def tools_in_order(expected: tuple[str, ...], called: list[str]) -> bool:
    """Whether the expected tools the agent called were first called in the
    order the question lists them.
    """
    first_calls = dict.fromkeys(tool for tool in called if tool in expected)
    positions = [expected.index(tool) for tool in first_calls]

    return positions == sorted(positions)


def cost(input_tokens: int, output_tokens: int, price: Price) -> float:
    """What the tokens cost, in dollars."""
    dollars = input_tokens * price.input + output_tokens * price.output

    return dollars / 1_000_000


def is_solved(
    question: GoldenQuestion,
    observed: Outcome,
    found: int,
    pages_cited: int,
    verdict: Verdict | None,
) -> bool:
    """A refusal or a clarification is solved when it is what was expected. An
    answer is solved when it is correct and cites an expected page, if the question
    has any. The judge says whether it is correct; with no verdict, it is correct
    when it holds every expected fact.
    """
    if question.expected_outcome != Outcome.ANSWER:
        return observed == question.expected_outcome

    if observed in (Outcome.REFUSE, Outcome.FAILED):
        return False

    if verdict is None:
        is_correct = found == len(question.expected_facts)
    else:
        is_correct = verdict.correct
    cites_a_page = pages_cited > 0 or not question.expected_pages

    return is_correct and cites_a_page


def summarise(scores: list[Score]) -> list[Summary]:
    """One summary per category, in the order the categories first appear, then
    one for all of them named "overall".
    """
    categories = dict.fromkeys(score.category for score in scores)
    summaries = [
        _add_up(name, [s for s in scores if s.category == name]) for name in categories
    ]

    return [*summaries, _add_up("overall", scores)]


def _add_up(name: str, scores: list[Score]) -> Summary:
    return Summary(
        name=name,
        questions=len(scores),
        solved=sum(s.solved for s in scores),
        judged=sum(s.judge_correct is not None for s in scores),
        judge_correct=sum(s.judge_correct is True for s in scores),
        facts_found=sum(s.facts_found for s in scores),
        facts_expected=sum(s.facts_expected for s in scores),
        pages_cited=sum(s.pages_cited for s in scores),
        pages_expected=sum(s.pages_expected for s in scores),
        cited_total=sum(s.cited_total for s in scores),
        tools_used=sum(s.tools_used for s in scores),
        tools_expected=sum(s.tools_expected for s in scores),
        refusals_right=sum(_refusal_is_right(s) for s in scores),
        seconds=sum(s.seconds for s in scores),
        tokens=sum(s.input_tokens + s.output_tokens for s in scores),
        cost=sum(s.cost for s in scores),
    )


def _refusal_is_right(score: Score) -> bool:
    # A failure neither refused nor answered, so it must not pass as "did not
    # refuse" on a question that expected an answer.
    if score.observed == Outcome.FAILED:
        return False

    refused = score.observed == Outcome.REFUSE
    should_refuse = score.expected == Outcome.REFUSE

    return refused == should_refuse


def _normal(text: str) -> str:
    """Lowercase words and numbers between single spaces, with the commas inside
    numbers dropped, so that a fact can be looked for as whole words.
    """
    without_separators = re.sub(r"(?<=\d),(?=\d{3})", "", text.lower())
    words = re.sub(r"\W+", " ", without_separators).strip()

    return f" {words} "


def _without_reality(title: str) -> str:
    return re.sub(r" \([^)]*\)$", "", title)
